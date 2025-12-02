import math

# Tobin Bridge location (Center of main span)
BRIDGE_LAT = 42.385024832115086
BRIDGE_LON = -71.04757879955105

# Tobin Bridge piers (GPS coordinates provided)
TOBIN_BRIDGE_PIERS = {
    'pier_1': {
        'name': 'Pier 1',
        'lat': 42.38406915832355,
        'lon': -71.04840495874075,
        'lateral_capacity_kips': 5000,
        'water_depth_ft': 35
    },
    'pier_2': {
        'name': 'Pier 2',
        'lat': 42.38588485861366,
        'lon': -71.04676244000547,
        'lateral_capacity_kips': 5000,
        'water_depth_ft': 35
    },
    'pier_3': {
        'name': 'Pier 3',
        'lat': 42.386689729342,
        'lon': -71.04601512671925,
        'lateral_capacity_kips': 5000,
        'water_depth_ft': 35
    }
}

def estimate_dwt_from_ais(ship_type, length, width):
    """Estimate vessel DWT based on AIS data"""
    if length is None or length == 0:
        if "CARGO" in str(ship_type).upper() or "CONTAINER" in str(ship_type).upper():
            return 15000
        elif "TANKER" in str(ship_type).upper():
            return 20000
        elif "PASSENGER" in str(ship_type).upper() or "FERRY" in str(ship_type).upper():
            return 1000
        else:
            return 5000

    if length > 250:
        return 50000
    elif length > 150:
        return 20000
    elif length > 100:
        return 10000
    elif length > 50:
        return 3000
    else:
        return 1000

def estimate_vessel_draft(dwt_tons, ship_type):
    """Estimate vessel draft based on DWT"""
    if dwt_tons > 50000:
        return 45
    elif dwt_tons > 20000:
        return 35
    elif dwt_tons > 10000:
        return 28
    elif dwt_tons > 5000:
        return 22
    elif dwt_tons > 1000:
        return 15
    else:
        return 10

def check_grounding_risk(vessel_draft_ft, water_depth_ft):
    """
    Two-category grounding assessment:
    1. WILL GROUND - clearance deficit > 10 ft
    2. POTENTIAL THREAT - vessel could reach pier

    Returns:
        will_ground: Boolean
        clearance: Under-keel clearance (feet)
    """
    clearance = water_depth_ft - vessel_draft_ft
    GROUNDING_THRESHOLD = -10  # feet deficit
    will_ground = (clearance < GROUNDING_THRESHOLD)
    return will_ground, clearance

def calculate_impact_force_aashto(dwt_long_tons, speed_knots):
    """AASHTO simplified formula: P = (V² × DWT × C) / (2g)"""
    speed_fps = speed_knots * 1.688
    C = 1.2
    g = 32.2
    force_kips = (speed_fps**2 * dwt_long_tons * C) / (2 * g)
    return force_kips

def calculate_dc_ratio(impact_force_kips, pier_capacity_kips):
    """Calculate Demand/Capacity ratio"""
    if pier_capacity_kips == 0:
        return 0
    return impact_force_kips / pier_capacity_kips

def assess_threat_level(dc_ratio):
    """Assess threat based on D/C ratio"""
    if dc_ratio >= 1.0:
        return "CRITICAL", "🔴", "Impact exceeds lateral pier capacity"
    elif dc_ratio >= 0.75:
        return "WARNING", "🟠", "Impact approaching lateral capacity"
    elif dc_ratio >= 0.50:
        return "WATCH", "🟡", "Significant lateral impact force"
    else:
        return "NORMAL", "🟢", "Impact within safe limits"

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula - distance in nautical miles"""
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    radius_nm = 3440.065
    distance = radius_nm * c
    return distance

def find_closest_pier(lat, lon):
    """Determine which pier is closest to vessel"""
    min_distance = float('inf')
    closest_pier = None

    for pier_id, pier_data in TOBIN_BRIDGE_PIERS.items():
        distance = calculate_distance(lat, lon, pier_data['lat'], pier_data['lon'])
        if distance < min_distance:
            min_distance = distance
            closest_pier = pier_id

    return closest_pier, min_distance

def analyze_vessel(ship_data):
    """Complete vessel analysis"""
    lat = ship_data.get('Latitude')
    lon = ship_data.get('Longitude')
    speed = ship_data.get('Sog', 0)
    ship_type = ship_data.get('ShipType', 'Unknown')

    dims = ship_data.get('Dimension', {})
    length = dims.get('A', 0) + dims.get('B', 0) if dims else 0
    width = dims.get('C', 0) + dims.get('D', 0) if dims else 0

    closest_pier_id, distance_to_pier = find_closest_pier(lat, lon)
    pier = TOBIN_BRIDGE_PIERS[closest_pier_id]
    distance_from_bridge = calculate_distance(lat, lon, BRIDGE_LAT, BRIDGE_LON)

    dwt = estimate_dwt_from_ais(ship_type, length, width)
    draft = estimate_vessel_draft(dwt, ship_type)
    will_ground, ukc = check_grounding_risk(draft, pier['water_depth_ft'])

    if will_ground:
        impact_force = 0
        dc_ratio = 0
        status = "GROUNDED"
        emoji = "⚓"
        description = f"Vessel will ground before pier (UKC deficit: {abs(ukc):.1f} ft)"
    else:
        impact_force = calculate_impact_force_aashto(dwt, speed)
        dc_ratio = calculate_dc_ratio(impact_force, pier['lateral_capacity_kips'])
        status, emoji, description = assess_threat_level(dc_ratio)

        if ukc < 5:
            description += f" | Marginal clearance (UKC: {ukc:+.1f} ft)"

    return {
        'closest_pier_id': closest_pier_id,
        'pier_name': pier['name'],
        'distance_to_pier_nm': distance_to_pier,
        'distance_from_bridge_nm': distance_from_bridge,
        'dwt_tons': dwt,
        'vessel_draft_ft': draft,
        'water_depth_ft': pier['water_depth_ft'],
        'ukc_ft': ukc,
        'will_ground': will_ground,
        'impact_force_kips': impact_force,
        'pier_lateral_capacity_kips': pier['lateral_capacity_kips'],
        'dc_ratio': dc_ratio,
        'status': status,
        'emoji': emoji,
        'description': description
    }

def predict_position(lat, lon, speed_knots, course_degrees, time_minutes):
    """
    Predict vessel position after given time

    Args:
        lat: Current latitude (degrees)
        lon: Current longitude (degrees)
        speed_knots: Vessel speed (knots)
        course_degrees: Vessel course (degrees, 0-360)
        time_minutes: Time ahead to predict (minutes)

    Returns:
        predicted_lat, predicted_lon: Future position
    """
    # Convert to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    course_rad = math.radians(course_degrees)

    # Distance traveled in nautical miles
    distance_nm = speed_knots * (time_minutes / 60.0)

    # Earth radius in nautical miles
    earth_radius_nm = 3440.065

    # Calculate new position using spherical trigonometry
    d_over_r = distance_nm / earth_radius_nm

    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(d_over_r) +
        math.cos(lat_rad) * math.sin(d_over_r) * math.cos(course_rad)
    )

    new_lon_rad = lon_rad + math.atan2(
        math.sin(course_rad) * math.sin(d_over_r) * math.cos(lat_rad),
        math.cos(d_over_r) - math.sin(lat_rad) * math.sin(new_lat_rad)
    )

    # Convert back to degrees
    new_lat = math.degrees(new_lat_rad)
    new_lon = math.degrees(new_lon_rad)

    return new_lat, new_lon

def calculate_closest_point_of_approach(ship_lat, ship_lon, speed_knots, course_degrees,
                                       target_lat, target_lon):
    """
    Calculate closest point of approach (CPA) to a target

    Args:
        ship_lat, ship_lon: Current vessel position
        speed_knots: Vessel speed
        course_degrees: Vessel course
        target_lat, target_lon: Target position (pier)

    Returns:
        cpa_distance_nm: Closest approach distance (nautical miles)
        cpa_time_minutes: Time until CPA (minutes)
        will_approach: Boolean - is vessel getting closer?
    """
    # If ship is stationary, CPA is current distance
    if speed_knots < 0.5:
        current_distance = calculate_distance(ship_lat, ship_lon, target_lat, target_lon)
        return current_distance, 0, False

    # Calculate positions at future time intervals
    current_distance = calculate_distance(ship_lat, ship_lon, target_lat, target_lon)
    min_distance = current_distance
    min_distance_time = 0

    # Check distances at 1-minute intervals for next 60 minutes
    for t in range(1, 61):
        future_lat, future_lon = predict_position(ship_lat, ship_lon, speed_knots,
                                                   course_degrees, t)
        future_distance = calculate_distance(future_lat, future_lon, target_lat, target_lon)

        if future_distance < min_distance:
            min_distance = future_distance
            min_distance_time = t

        # If distance starts increasing after decreasing, we've passed CPA
        if t > min_distance_time + 5 and future_distance > min_distance:
            break

    # Vessel is approaching if CPA is in the future and closer than current position
    will_approach = (min_distance < current_distance) and (min_distance_time > 0)

    return min_distance, min_distance_time, will_approach

def predict_trajectory(ship_data, prediction_times=[5, 10, 15]):
    """
    Predict vessel trajectory at multiple time intervals

    Args:
        ship_data: Dictionary with current vessel data
        prediction_times: List of future times in minutes

    Returns:
        trajectory: List of predicted positions with analysis
    """
    lat = ship_data.get('Latitude')
    lon = ship_data.get('Longitude')
    speed = ship_data.get('Sog', 0)
    course = ship_data.get('Cog', 0)

    trajectory = []

    for t in prediction_times:
        pred_lat, pred_lon = predict_position(lat, lon, speed, course, t)

        # Calculate distance to bridge at predicted position
        distance_to_bridge = calculate_distance(pred_lat, pred_lon, BRIDGE_LAT, BRIDGE_LON)

        trajectory.append({
            'time_minutes': t,
            'latitude': pred_lat,
            'longitude': pred_lon,
            'distance_to_bridge_nm': distance_to_bridge
        })

    return trajectory

def assess_collision_risk(ship_data, analysis):
    """
    Assess collision risk based on trajectory, speed, distance, and impact force

    Args:
        ship_data: Vessel AIS data
        analysis: Existing vessel analysis with D/C ratio

    Returns:
        collision_assessment: Dictionary with risk details
    """
    lat = ship_data.get('Latitude')
    lon = ship_data.get('Longitude')
    speed = ship_data.get('Sog', 0)
    course = ship_data.get('Cog', 0)

    # Find CPA to closest pier
    closest_pier_id = analysis['closest_pier_id']
    pier = TOBIN_BRIDGE_PIERS[closest_pier_id]
    distance_to_pier = analysis['distance_to_pier_nm']

    cpa_distance, cpa_time, will_approach = calculate_closest_point_of_approach(
        lat, lon, speed, course,
        pier['lat'], pier['lon']
    )

    dc_ratio = analysis['dc_ratio']
    will_ground = analysis['will_ground']

    # Check if vessel is approaching (getting closer to bridge)
    if speed > 0.5:
        future_lat, future_lon = predict_position(lat, lon, speed, course, 5)
        future_distance = calculate_distance(future_lat, future_lon, pier['lat'], pier['lon'])
        approaching = future_distance < distance_to_pier
    else:
        approaching = False

    # Assess risk level

    # NEGLIGIBLE THREAT: Grounded, small, far, or heading away
    if will_ground:
        risk_level = "NEGLIGIBLE THREAT"
        risk_description = "Vessel will ground before pier"

    elif not approaching and distance_to_pier > 1.0:
        risk_level = "NEGLIGIBLE THREAT"
        risk_description = "Vessel headed away - Routine tracking"

    elif dc_ratio < 0.5:
        risk_level = "NEGLIGIBLE THREAT"
        risk_description = "Vessel too small - Routine tracking"

    elif distance_to_pier > 10:
        risk_level = "NEGLIGIBLE THREAT"
        risk_description = "Vessel far from bridge - Routine tracking"

    elif speed < 0.5:
        risk_level = "NEGLIGIBLE THREAT"
        risk_description = "Vessel stationary - Routine tracking"

    # ALARM: Excessive speed + approaching
    elif dc_ratio >= 1.0 and speed > 15 and approaching and distance_to_pier < 2:
        risk_level = "ALARM"
        risk_description = "Excessive speed approaching bridge - Close bridge immediately"

    # ELEVATED MONITORING: Large vessel approaching (normal transit)
    elif dc_ratio >= 0.75 and approaching and distance_to_pier < 5:
        risk_level = "ELEVATED MONITORING"
        risk_description = "Large vessel approaching - Routine transit expected"

    # MONITOR: Large vessel in area
    elif dc_ratio >= 0.5 and distance_to_pier < 10:
        risk_level = "MONITOR"
        risk_description = "Large vessel in the area - Routine tracking"

    # NEGLIGIBLE THREAT: Everything else
    else:
        risk_level = "NEGLIGIBLE THREAT"
        risk_description = "Vessel too small, deep drafted, far, or headed away - Routine tracking"

    return {
        'risk_level': risk_level,
        'risk_description': risk_description,
        'cpa_distance_nm': cpa_distance,
        'cpa_time_minutes': cpa_time,
        'will_approach': will_approach,
        'time_to_impact': cpa_time if approaching else None,
        'approaching': approaching
    }

def calculate_allision_probability(ship_data, analysis, collision_risk):
    """
    Calculate probability of vessel allision with bridge pier

    Accounts for multiple uncertainty factors:
    - Trajectory deviation probability
    - Grounding probability
    - Maneuvering ability
    - Environmental factors

    Args:
        ship_data: Vessel AIS data
        analysis: Vessel analysis with D/C ratio
        collision_risk: Collision assessment with CPA

    Returns:
        probability: Float 0-1 (0% to 100%)
        confidence: String describing confidence level
        factors: Dictionary of contributing factors
    """
    speed = ship_data.get('Sog', 0)

    # Initialize probability factors
    factors = {}

    # Factor 1: Trajectory alignment (0-1)
    # How directly is vessel heading toward pier?
    cpa_distance = collision_risk['cpa_distance_nm']
    will_approach = collision_risk['will_approach']

    if not will_approach:
        trajectory_factor = 0.0
        factors['trajectory'] = "Vessel heading away from bridge"
    elif cpa_distance > 0.5:
        trajectory_factor = 0.0
        factors['trajectory'] = f"CPA {cpa_distance:.2f} nm - safe passage"
    elif cpa_distance > 0.3:
        trajectory_factor = 0.2
        factors['trajectory'] = f"CPA {cpa_distance:.2f} nm - marginal"
    elif cpa_distance > 0.1:
        trajectory_factor = 0.5
        factors['trajectory'] = f"CPA {cpa_distance:.2f} nm - close approach"
    else:
        trajectory_factor = 0.9
        factors['trajectory'] = f"CPA {cpa_distance:.2f} nm - collision course"

    # Factor 2: Grounding probability (0-1)
    # Will vessel ground before reaching pier?
    ukc = analysis['ukc_ft']

    if analysis['will_ground']:
        grounding_prevents = 0.95  # High confidence vessel will ground
        factors['grounding'] = f"UKC {ukc:.1f} ft - will likely ground"
    elif ukc < -5:
        grounding_prevents = 0.7  # Probable grounding
        factors['grounding'] = f"UKC {ukc:.1f} ft - probable grounding"
    elif ukc < 0:
        grounding_prevents = 0.4  # Possible grounding
        factors['grounding'] = f"UKC {ukc:.1f} ft - possible grounding"
    elif ukc < 5:
        grounding_prevents = 0.1  # Unlikely grounding
        factors['grounding'] = f"UKC {ukc:.1f} ft - marginal clearance"
    else:
        grounding_prevents = 0.0  # No grounding expected
        factors['grounding'] = f"UKC {ukc:.1f} ft - adequate depth"

    # Factor 3: Vessel maneuvering ability (0-1)
    # Can vessel avoid collision if needed?
    distance_to_pier = analysis['distance_to_pier_nm']

    if speed < 0.5:
        maneuver_factor = 0.0  # Stationary vessel
        factors['maneuverability'] = "Stationary - minimal drift risk"
    elif speed < 5 and distance_to_pier > 1.0:
        maneuver_factor = 0.1  # Slow speed, good distance
        factors['maneuverability'] = "Low speed - can maneuver"
    elif speed < 10 and distance_to_pier > 0.5:
        maneuver_factor = 0.3  # Moderate speed, adequate distance
        factors['maneuverability'] = "Moderate speed - should maneuver"
    elif distance_to_pier > 0.3:
        maneuver_factor = 0.5  # Fast but some distance
        factors['maneuverability'] = f"{speed:.1f} kts - limited time to maneuver"
    else:
        maneuver_factor = 0.8  # Fast and close
        factors['maneuverability'] = f"{speed:.1f} kts at {distance_to_pier:.2f} nm - minimal time"

    # Factor 4: Impact severity if collision occurs (0-1)
    # Based on D/C ratio
    dc_ratio = analysis['dc_ratio']

    if dc_ratio < 0.5:
        severity_factor = 0.3  # Minor damage likely
        factors['severity'] = f"D/C={dc_ratio:.2f} - minor damage if impact"
    elif dc_ratio < 0.75:
        severity_factor = 0.5  # Moderate damage likely
        factors['severity'] = f"D/C={dc_ratio:.2f} - moderate damage if impact"
    elif dc_ratio < 1.0:
        severity_factor = 0.7  # Significant damage likely
        factors['severity'] = f"D/C={dc_ratio:.2f} - significant damage if impact"
    else:
        severity_factor = 1.0  # Pier failure likely
        factors['severity'] = f"D/C={dc_ratio:.2f} - pier failure if impact"

    # Calculate combined probability
    # P(allision) = P(on trajectory) × P(doesn't ground) × P(fails to maneuver) × Severity

    base_probability = trajectory_factor * (1 - grounding_prevents) * maneuver_factor

    # Weight by severity for risk prioritization
    risk_weighted_probability = base_probability * severity_factor

    # Determine confidence level
    if trajectory_factor == 0 or grounding_prevents > 0.9:
        confidence = "HIGH"
        confidence_desc = "High confidence in assessment"
    elif ukc < 5 or distance_to_pier < 0.5:
        confidence = "MODERATE"
        confidence_desc = "Moderate confidence - uncertainties present"
    else:
        confidence = "LOW"
        confidence_desc = "Low confidence - multiple uncertainties"

    # Categorize probability
    if risk_weighted_probability < 0.05:
        probability_category = "NEGLIGIBLE"
        category_emoji = "🟢"
    elif risk_weighted_probability < 0.15:
        probability_category = "LOW"
        category_emoji = "🟡"
    elif risk_weighted_probability < 0.35:
        probability_category = "MODERATE"
        category_emoji = "🟠"
    else:
        probability_category = "HIGH"
        category_emoji = "🔴"

    return {
        'probability': risk_weighted_probability,
        'probability_percent': risk_weighted_probability * 100,
        'probability_category': probability_category,
        'category_emoji': category_emoji,
        'confidence': confidence,
        'confidence_description': confidence_desc,
        'factors': factors,
        'base_probability': base_probability,
        'severity_factor': severity_factor
    }
