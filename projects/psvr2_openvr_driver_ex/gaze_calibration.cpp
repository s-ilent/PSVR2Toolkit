#include "gaze_calibration.h"
#include "vr_settings.h" // Provides psvr2_toolkit::VRSettings

#include <algorithm>
#include <cmath>
#include <optional>
#include <sstream>

namespace
{
    // Configuration keys used in steamvr.vrsettings
    constexpr auto CALIBRATION_KEY_SUFFIX = "Calibration";
    constexpr auto CENTER_KEY_SUFFIX = "Center";

    // Values in the config file are scaled by this factor for human readability.
    constexpr double CONFIG_SCALE = 100.0;
    constexpr double PI = 3.14159265358979323846;
    constexpr double TAU = 2.0 * PI;

    // --- General Utilities ---

    std::vector<std::string> SplitString(const std::string& str, char delim)
    {
        std::vector<std::string> tokens;
        if (str.empty()) return tokens;
        std::stringstream ss(str);
        std::string token;
        while (std::getline(ss, token, delim))
        {
            tokens.push_back(token);
        }
        return tokens;
    }

    template <typename T>
    bool TryParse(const std::string& str, T* result)
    {
        std::stringstream ss(str);
        T value;
        ss >> value;
        if (ss.fail() || !ss.eof()) return false;
        *result = value;
        return true;
    }

    // --- Geometric Utilities ---

    /**
     * @brief Calculates the distance from a ray's origin to its intersection
     * with a line segment defined by two points.
     * @return Distance to intersection, or nullopt if no intersection.
     */
    std::optional<double> FindRaySegmentIntersection(Vec2d ray_dir, Vec2d p1, Vec2d p2) {
        const auto segment_vec = Vec2d{ p1.x - p2.x, p1.y - p2.y };
        const auto ray_normal = Vec2d{ -ray_dir.y, ray_dir.x };
        const double dot = (segment_vec.x * ray_normal.x) + (segment_vec.y * ray_normal.y);

        if (std::abs(dot) < 1e-5) return std::nullopt; // Parallel lines

        const double t = ((p1.x * ray_normal.x) + (p1.y * ray_normal.y)) / dot;
        if (t < -1e-5 || t > 1.0 + 1e-5) return std::nullopt; // Intersection is outside the segment

        const double cross_product = p2.x * p1.y - p2.y * p1.x;
        return cross_product / dot;
    }

    Vec2d PolarToCartesian(double angle, double length) {
        return { std::cos(angle) * length, std::sin(angle) * length };
    }

} // Anonymous namespace

void GazeCalibrationProfile::LoadConfig(const std::string& eye_section)
{
    // Construct the keys to look for in the settings file.
    const std::string center_key = eye_section + "_" + CENTER_KEY_SUFFIX;
    const std::string cal_key = eye_section + "_" + CALIBRATION_KEY_SUFFIX;

    // Load the center offset using the helper, providing a default value.
    const std::string center_str = psvr2_toolkit::VRSettings::GetString(center_key.c_str(), "0.0 0.0");
    const auto center_data = SplitString(center_str, ' ');
    m_center = { 0.0, 0.0 };
    if (center_data.size() == 2) {
        double cx = 0.0, cy = 0.0;
        if (TryParse(center_data[0], &cx)) m_center.x = cx / CONFIG_SCALE;
        if (TryParse(center_data[1], &cy)) m_center.y = cy / CONFIG_SCALE;
    }

    // Load the calibration data using the helper.
    const std::string cal_str = psvr2_toolkit::VRSettings::GetString(cal_key.c_str(), "");
    m_calibration.clear();
    if (!cal_str.empty()) {
        const auto cal_data = SplitString(cal_str, ' ');
        m_calibration.reserve(cal_data.size());
        for (const auto& sample_str : cal_data) {
            double sample = 1.0;
            TryParse(sample_str, &sample); // Default to 1.0 on parse failure.
            m_calibration.push_back(sample / CONFIG_SCALE);
        }
    }
}

Hmd2Vector3 GazeCalibrationProfile::Remap(const Hmd2Vector3& raw_gaze_dir) const
{
    // 1. Apply the center offset to the raw gaze coordinates.
    double x = raw_gaze_dir.x - m_center.x;
    double y = raw_gaze_dir.y - m_center.y;

    // If no calibration data is loaded, return the centered position as a fallback.
    if (m_calibration.empty())
    {
        return { (float)x, (float)y, raw_gaze_dir.z };
    }

    // 2. Convert the centered Cartesian coordinates to polar coordinates.
    double angle = std::atan2(y, x);
    if (angle < 0) angle += TAU; // Ensure angle is in the [0, 2PI] range.

    const double raw_distance = std::sqrt(x * x + y * y);

    // 3. Get the expected raw distance (radius) from the calibration polygon at this angle.
    const double calibrated_radius = GetInterpolatedRadiusAtAngle(angle);

    // 4. Normalize the raw distance by the expected distance from calibration.
    const double scale = (calibrated_radius > 1e-6) ? calibrated_radius : 1.0;
    const double normalized_distance = raw_distance / scale;

    // 5. Convert the remapped polar coordinates back to Cartesian coordinates.
    const auto final_x = static_cast<float>(std::cos(angle) * normalized_distance);
    const auto final_y = static_cast<float>(std::sin(angle) * normalized_distance);

    return { final_x, final_y, raw_gaze_dir.z };
}

double GazeCalibrationProfile::GetInterpolatedRadiusAtAngle(double angle) const
{
    const size_t num_samples = m_calibration.size();
    if (num_samples == 0) return 1.0;

    // Determine which two calibration points the current angle falls between.
    const double angular_pos = angle / TAU * num_samples;
    const size_t prev_index = static_cast<size_t>(angular_pos) % num_samples;
    if (num_samples == 1) return m_calibration[prev_index];

    const size_t next_index = (prev_index + 1) % num_samples;

    // Get the positions of these two calibration points.
    const double prev_angle = prev_index * TAU / num_samples;
    const double next_angle = next_index * TAU / num_samples;
    const Vec2d p1 = PolarToCartesian(prev_angle, m_calibration[prev_index]);
    const Vec2d p2 = PolarToCartesian(next_angle, m_calibration[next_index]);

    // Find the radius by intersecting a ray with the line segment between the points.
    const Vec2d ray_dir = PolarToCartesian(angle, 1.0);
    const auto intersection = FindRaySegmentIntersection(ray_dir, p1, p2);

    // As a fallback, use the nearest point if intersection fails.
    return intersection.value_or(m_calibration[prev_index]);
}