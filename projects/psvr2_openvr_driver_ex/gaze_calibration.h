#pragma once

#include <string>
#include <vector>
#include "hmd2_gaze.h" // Provides Hmd2Vector3

// A simple 2D vector for internal calculations.
struct Vec2d
{
    double x = 0.0;
    double y = 0.0;
};

/**
 * @brief Manages the calibration profile for a single eye.
 * This class loads calibration data from settings and applies the necessary
 * transformations to remap raw gaze data into a normalized space.
 */
class GazeCalibrationProfile
{
public:
    // A list of scale factors representing the radius of the raw gaze input
    // at equidistant angles around a 360-degree circle.
    using CalibrationData = std::vector<double>;

    /**
     * @brief Remaps a raw gaze direction vector using the loaded calibration profile.
     * @param raw_gaze_dir The raw {x, y, z} vector from the eye tracker.
     * @return A new, calibrated {x, y, z} vector.
     */
    Hmd2Vector3 Remap(const Hmd2Vector3& raw_gaze_dir) const;

    /**
     * @brief Loads the center offset and polygonal calibration data from SteamVR settings.
     * @param eye_section The identifier for the eye, e.g., "LeftEye".
     */
    void LoadConfig(const std::string& eye_section);

    const CalibrationData& GetCalibrationData() const { return m_calibration; }

private:
    /**
     * @brief Calculates the calibrated radius for a given angle.
     * Treats the calibration data as vertices of a polygon and finds the radius
     * by calculating the intersection of a ray at the given angle with the
     * line segment connecting the two nearest vertices.
     * @param angle The angle of the gaze in radians [0, 2PI].
     * @return The interpolated radius (scale factor).
     */
    double GetInterpolatedRadiusAtAngle(double angle) const;

    // A 2D offset to correct for the resting position of the user's gaze.
    Vec2d m_center = { 0.0, 0.0 };

    // Defines the polygonal shape of the raw input, used for normalization.
    CalibrationData m_calibration;
};