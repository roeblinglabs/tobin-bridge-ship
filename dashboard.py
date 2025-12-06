import streamlit as st
import folium
from streamlit_folium import st_folium
from vessel_analysis import (analyze_vessel, TOBIN_BRIDGE_PIERS, BRIDGE_LAT, BRIDGE_LON,
                             predict_trajectory, assess_collision_risk, calculate_allision_probability)

# Page configuration
st.set_page_config(
    page_title="Tobin Bridge Vessel Monitor",
    page_icon="🚢",
    layout="wide"
)

# Header with logo
logo_col, title_col = st.columns([1, 5])

with logo_col:
    st.image("Logo-Roebling-Labs.webp", width=150)

with title_col:
    st.title("🌉 Tobin Bridge Vessel Collision Warning System")
    st.markdown("**Roebling Labs LLC** | Vessel tracking, trajectory forecasting, and AASHTO bridge impact analysis")

st.markdown("---")

# Create columns for layout
col1, col2 = st.columns([2, 1])

# Function to get ship color based on NEW threat level system
def get_ship_color(risk_level):
    """Get marker color based on NEW threat level system"""
    colors = {
        'ALARM': 'red',
        'ELEVATED MONITORING': 'orange',
        'MONITOR': 'yellow',
        'NEGLIGIBLE THREAT': 'green',
        'GROUNDED': 'gray'
    }
    return colors.get(risk_level, 'blue')

def get_real_ships():
    """Load ships from JSON file (updated manually)"""
    import json
    import os
    import datetime
    from zoneinfo import ZoneInfo

    json_file = 'current_ships.json'

    # Check if file exists
    if not os.path.exists(json_file):
        st.warning("⚠️ No ship data file found. Run 'python3 update_ships.py' to fetch current ships.")
        return get_mock_ships_fallback(), None

    try:
        # Load ships from JSON
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Check if data has new structure with timestamp
        if isinstance(data, dict) and 'timestamp' in data and 'vessels' in data:
            # New format with timestamp
            update_time = datetime.datetime.fromisoformat(data['timestamp'])
            ships_data = data['vessels']
        else:
            # Old format (just array of vessels) - use file modification time
            file_time = os.path.getmtime(json_file)
            update_time = datetime.datetime.fromtimestamp(file_time, tz=ZoneInfo('America/New_York'))
            ships_data = data

        ships = []
        for ship in ships_data:
            # Analyze vessel
            analysis = analyze_vessel(ship)
            ship['analysis'] = analysis
            ship['trajectory'] = predict_trajectory(ship)
            ship['collision_risk'] = assess_collision_risk(ship, analysis)
            ship['allision_probability'] = calculate_allision_probability(
                ship, analysis, ship['collision_risk'])
            ships.append(ship)

        return ships, update_time

    except Exception as e:
        st.error(f"Error loading ship data: {e}")
        return get_mock_ships_fallback(), None

def get_mock_ships_fallback():
    """Fallback mock data if API fails"""
    mock_ships = [
        {'name': 'DEMO VESSEL 1', 'mmsi': '000000001', 'type': 'Cargo',
         'Latitude': 42.38, 'Longitude': -71.06,
         'Sog': 8.0, 'Cog': 45.0, 'ShipType': 'Cargo',
         'Dimension': {'A': 75, 'B': 75, 'C': 12, 'D': 12}},
        {'name': 'DEMO VESSEL 2', 'mmsi': '000000002', 'type': 'Passenger',
         'Latitude': 42.39, 'Longitude': -71.03,
         'Sog': 12.0, 'Cog': 225.0, 'ShipType': 'Passenger',
         'Dimension': {'A': 40, 'B': 40, 'C': 8, 'D': 8}}
    ]

    for ship in mock_ships:
        analysis = analyze_vessel(ship)
        ship['analysis'] = analysis
        ship['trajectory'] = predict_trajectory(ship)
        ship['collision_risk'] = assess_collision_risk(ship, analysis)
        ship['allision_probability'] = calculate_allision_probability(
            ship, analysis, ship['collision_risk'])

    return mock_ships

# Get ships
with st.spinner("Loading vessel data..."):
    ships, update_time = get_real_ships()

with col1:
    st.subheader("📍 Map of Bridge, Piers, Vessels, and Trajectories")

    # Create map centered on Tobin Bridge
    m = folium.Map(
        location=[BRIDGE_LAT, BRIDGE_LON],
        zoom_start=13,
        tiles=None  # Start with no tiles, add custom layers below
    )

    # Add OpenStreetMap as base layer
    folium.TileLayer(
        tiles='https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        attr='© OpenStreetMap contributors',
        name='OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(m)

    # Add NOAA ENC nautical charts as alternative base layer (via ArcGIS REST)
    folium.WmsTileLayer(
        url='https://gis.charttools.noaa.gov/arcgis/rest/services/MCS/ENCOnline/MapServer/exts/MaritimeChartService/WMSServer',
        layers='0,1,2,3,4,5,6,7',
        fmt='image/png',
        transparent=True,
        attr='© NOAA',
        name='NOAA Nautical Charts',
        overlay=False,
        control=True
    ).add_to(m)

    # Add OpenSeaMap nautical chart overlay (works on top of any base layer)
    folium.TileLayer(
        tiles='https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png',
        attr='© OpenSeaMap contributors',
        name='OpenSeaMap Overlay',
        overlay=True,
        control=True
    ).add_to(m)

    # Add Tobin Bridge marker (BLUE - infrastructure)
    folium.Marker(
        [BRIDGE_LAT, BRIDGE_LON],
        popup="Tobin Bridge",
        tooltip="Tobin Bridge",
        icon=folium.Icon(color='blue', icon='bridge', prefix='fa')
    ).add_to(m)

    # Add pier markers (BLUE - infrastructure)
    for pier_id, pier_data in TOBIN_BRIDGE_PIERS.items():
        folium.CircleMarker(
            location=[pier_data['lat'], pier_data['lon']],
            radius=10,
            popup=pier_data['name'],
            tooltip=f"{pier_data['name']}<br>Lateral Capacity: {pier_data['lateral_capacity_kips']} kips",
            color='darkblue',
            fill=True,
            fillColor='blue',
            fillOpacity=0.7
        ).add_to(m)

    # Add ships to map with trajectories
    if ships:
        for ship in ships:
            analysis = ship['analysis']
            trajectory = ship.get('trajectory', [])
            allision_prob = ship.get('allision_probability', {})
            collision_risk = ship.get('collision_risk', {})

            # Get color based on NEW threat level system
            risk_level = collision_risk.get('risk_level', 'NEGLIGIBLE THREAT')
            color = get_ship_color(risk_level)

            # Color mapping for consistent display
            color_css_map = {
                'red': '#dc3545',
                'orange': '#fd7e14',
                'yellow': '#ffeb3b',  # Brighter yellow for better visibility
                'green': '#28a745',
                'blue': '#007bff',
                'gray': '#6c757d'
            }
            color_css = color_css_map.get(color, '#007bff')

            # Draw trajectory line if vessel is moving
            if ship['Sog'] > 0.05 and trajectory:
                trajectory_coords = [[ship['Latitude'], ship['Longitude']]]
                for point in trajectory:
                    trajectory_coords.append([point['latitude'], point['longitude']])

                folium.PolyLine(
                    trajectory_coords,
                    color=color_css,
                    weight=2,
                    opacity=0.6,
                    dash_array='5, 5',
                    popup=f"{ship['name']} - Predicted Path"
                ).add_to(m)

                # Add arrow markers at trajectory points showing direction of travel
                for point in trajectory:
                    # Create arrow marker pointing in direction of course
                    arrow_icon = folium.DivIcon(html=f"""
                        <div style="transform: rotate({ship['Cog']}deg); font-size: 20px; color: {color_css};">
                            ▲
                        </div>
                    """)

                    folium.Marker(
                        [point['latitude'], point['longitude']],
                        icon=arrow_icon,
                        popup=f"{ship['name']}<br>+{point['time_minutes']} min linear projection"
                    ).add_to(m)

            # Create simplified popup
            ship_type = ship.get('ShipType', ship.get('type', 'Unknown'))
            approaching = collision_risk.get('approaching', False)
            time_to_arrival = collision_risk.get('cpa_time_minutes', 0)

            # Determine if vessel can endanger bridge
            can_endanger = "⚠️ YES" if analysis['dc_ratio'] >= 1.0 and not analysis['will_ground'] else "✓ No"

            # Build time to arrival text
            if ship['Sog'] < 0.05:
                arrival_text = "Stationary"
            elif approaching:
                arrival_text = f"{time_to_arrival:.0f} minutes"
            else:
                arrival_text = "Moving away"

            popup_html = f"""
            <div style="width: 280px">
                <h4>{ship['name']}</h4>
                <b>Threat Level:</b> {risk_level}<br>
                <b>Type:</b> {ship_type}<br>
                <b>Speed:</b> {ship['Sog']:.1f} knots | <b>Course:</b> {ship['Cog']:.1f}°<br>
                <b>Distance:</b> {analysis['distance_from_bridge_nm']:.2f} nm<br>
                <b>Time to Arrival:</b> {arrival_text}<br>
                <hr>
                <b>Can endanger bridge at current speed?</b> {can_endanger}
            </div>
            """

            # Create marker with pulsing animation for moving vessels
            is_moving = ship['Sog'] > 0.05

            # RGBA color mapping for pulse effect
            color_rgba_map = {
                'red': '220, 53, 69',
                'orange': '253, 126, 20',
                'yellow': '255, 235, 59',  # Brighter yellow for better visibility
                'green': '40, 167, 69',
                'blue': '0, 123, 255',
                'gray': '108, 117, 125'
            }
            color_rgba = color_rgba_map.get(color, '0, 123, 255')

            if is_moving:
                # Use custom DivIcon with pulsing animation for moving vessels
                # Create unique ID for this vessel to avoid CSS conflicts
                vessel_id = ship.get('mmsi', '').replace('.', '_')
                icon_html = f"""
                <div style="position: relative;">
                    <style>
                        @keyframes pulse-{vessel_id} {{
                            0% {{ box-shadow: 0 0 0 0 rgba({color_rgba}, 0.7); }}
                            50% {{ box-shadow: 0 0 0 10px rgba({color_rgba}, 0); }}
                            100% {{ box-shadow: 0 0 0 0 rgba({color_rgba}, 0); }}
                        }}
                        .marker-{vessel_id} {{
                            width: 30px;
                            height: 30px;
                            border-radius: 50%;
                            background: {color_css};
                            animation: pulse-{vessel_id} 2s infinite;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                            font-weight: bold;
                        }}
                    </style>
                    <div class="marker-{vessel_id}">
                        <i class="fa fa-ship"></i>
                    </div>
                </div>
                """
                marker_icon = folium.DivIcon(html=icon_html)
            else:
                # Static icon for stationary vessels (anchor symbol in light green)
                marker_icon = folium.Icon(color='lightgreen', icon='anchor', prefix='fa')

            folium.Marker(
                [ship['Latitude'], ship['Longitude']],
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=f"{ship['name']} - {risk_level}",
                icon=marker_icon
            ).add_to(m)

    # Add layer control to toggle between map layers (must be added last)
    folium.LayerControl(position='topleft', collapsed=True).add_to(m)

    # Display map
    st_folium(m, width=700, height=600)

    # Data freshness note under the map
    st.markdown("---")
    if update_time:
        st.info(f"""
        **📊 Ship Data:** Last updated {update_time.strftime('%I:%M %p')} Local Time ({update_time.strftime('%Z')}) on {update_time.strftime('%b %d, %Y')}

        **Note:** This demo uses vessel data pulled daily from AISStream.io for demonstration purposes.
        Production systems deploy a local AIS receiver at the bridge site for real-time vessel tracking,
        with computer vision backup for redundancy and visual verification.
        """)
    else:
        st.info("""
        **Note:** This demo uses simulated vessel data for demonstration purposes.
        Production systems deploy a local AIS receiver at the bridge site for real-time vessel tracking,
        with computer vision backup for redundancy and visual verification.
        """)

with col2:
    st.subheader("⚠️ Threat Assessment")

    if ships:
        # Count vessels in each category
        alarm_count = sum(1 for s in ships if s.get('collision_risk', {}).get('risk_level') == 'ALARM')
        elevated_count = sum(1 for s in ships if s.get('collision_risk', {}).get('risk_level') == 'ELEVATED MONITORING')
        monitor_count = sum(1 for s in ships if s.get('collision_risk', {}).get('risk_level') == 'MONITOR')
        negligible_count = sum(1 for s in ships if s.get('collision_risk', {}).get('risk_level') == 'NEGLIGIBLE THREAT')

        # Determine current overall status (highest priority with vessels)
        if alarm_count > 0:
            current_status = "🔴 ALARM"
            status_color = "error"
        elif elevated_count > 0:
            current_status = "🟠 ELEVATED MONITORING"
            status_color = "warning"
        elif monitor_count > 0:
            current_status = "🟡 MONITOR"
            status_color = "info"
        else:
            current_status = "🟢 NEGLIGIBLE THREAT"
            status_color = "success"

        # Display current status prominently
        if status_color == "error":
            st.error(f"### {current_status}")
        elif status_color == "warning":
            st.warning(f"### {current_status}")
        elif status_color == "info":
            st.info(f"### {current_status}")
        else:
            st.success(f"### {current_status}")

        # Show summary of all categories
        st.markdown(f"""
        **Total Vessels:** {len(ships)}
        - 🔴 **Alarm:** {alarm_count}
        - 🟠 **Elevated Monitoring:** {elevated_count}
        - 🟡 **Monitor:** {monitor_count}
        - 🟢 **Negligible Threat:** {negligible_count}
        """)
    else:
        st.success("### 🟢 NEGLIGIBLE THREAT")
        st.info("No vessels detected in monitoring area")

    st.subheader("🚢 Detected Vessels")

    if ships:
        # Sort vessels by threat level priority, then by distance
        threat_priority = {
            'ALARM': 1,
            'ELEVATED MONITORING': 2,
            'MONITOR': 3,
            'NEGLIGIBLE THREAT': 4
        }

        sorted_ships = sorted(ships, key=lambda s: (
            threat_priority.get(s.get('collision_risk', {}).get('risk_level', 'NEGLIGIBLE THREAT'), 999),
            s['analysis']['distance_to_pier_nm']
        ))

        for ship in sorted_ships:
            analysis = ship['analysis']
            collision_risk = ship.get('collision_risk', {})

            # Get threat level from collision risk
            risk_level = collision_risk.get('risk_level', 'NEGLIGIBLE THREAT')
            risk_emoji_map = {
                'ALARM': '🔴',
                'ELEVATED MONITORING': '🟠',
                'MONITOR': '🟡',
                'NEGLIGIBLE THREAT': '🟢'
            }
            risk_emoji = risk_emoji_map.get(risk_level, '⚪')

            with st.expander(f"{risk_emoji} {ship['name']} - {risk_level}", expanded=False):

                # VESSEL DATA (from AIS)
                st.markdown("**VESSEL DATA** *(from AIS transponder)*")
                ship_type = ship.get('ShipType', ship.get('type', 'Unknown'))
                heading = ship.get('Heading', 'N/A')  # AIS heading if available
                course = ship.get('Cog', 0)
                speed = ship.get('Sog', 0)

                # Calculate dimensions from AIS
                dim = ship.get('Dimension', {})
                length_m = dim.get('A', 0) + dim.get('B', 0)
                beam_m = dim.get('C', 0) + dim.get('D', 0)
                length_ft = length_m * 3.28084
                beam_ft = beam_m * 3.28084

                st.markdown(f"• **Type:** {ship_type}")
                if heading != 'N/A':
                    st.markdown(f"• **Speed:** {speed:.1f} knots | **Course:** {course:.1f}° | **Heading:** {heading}°")
                else:
                    st.markdown(f"• **Speed:** {speed:.1f} knots | **Course:** {course:.1f}°")

                if length_ft > 0 and beam_ft > 0:
                    st.markdown(f"• **Dimensions:** {length_ft:.0f} ft × {beam_ft:.0f} ft")
                st.markdown(f"• **MMSI:** {ship['mmsi']}")

                st.markdown("")

                # ESTIMATED VESSEL PROPERTIES
                st.markdown("**ESTIMATED VESSEL PROPERTIES**")
                st.markdown(f"• **Displacement:** ~{analysis['dwt_tons']:,} tons *(estimated from dimensions)*")
                st.markdown(f"• **Draft:** {analysis['vessel_draft_ft']:.0f} ft *(from AIS - crew reported)*")

                st.markdown("---")

                # CALCULATIONS
                st.markdown("**CALCULATIONS**")

                # Trajectory Analysis
                st.markdown("**Trajectory Analysis**")
                st.markdown(f"• Distance to bridge: {analysis['distance_from_bridge_nm']:.2f} nm")

                # Display pier name
                pier_display = analysis['pier_name']
                st.markdown(f"• Closest pier: {pier_display}")

                # Approaching status
                approaching = collision_risk.get('approaching', False)
                speed_check = ship.get('Sog', 0)

                if speed_check < 0.5:
                    st.markdown(f"• Status: **Stationary**")
                elif approaching:
                    st.markdown(f"• Status: **Approaching bridge**")
                else:
                    st.markdown(f"• Status: **Moving away from bridge**")

                # CPA
                cpa_distance = collision_risk.get('cpa_distance_nm', 0)
                st.markdown(f"• Will pass: {cpa_distance:.2f} nm from pier")

                # Time to Arrival
                if approaching:
                    cpa_time = collision_risk.get('cpa_time_minutes', 0)
                    st.markdown(f"• Time to Arrival: {cpa_time:.0f} minutes")
                else:
                    st.markdown(f"• Time to Arrival: Not applicable (moving away)")

                # Grounding risk
                ukc = analysis['ukc_ft']
                depth = analysis['water_depth_ft']
                draft = analysis['vessel_draft_ft']
                if ukc >= 10:
                    st.markdown(f"• Grounding risk: None (depth {depth:.0f} ft, draft {draft:.0f} ft, clearance +{ukc:.0f} ft)")
                elif ukc >= 0:
                    st.markdown(f"• Grounding risk: Low (depth {depth:.0f} ft, draft {draft:.0f} ft, clearance +{ukc:.0f} ft)")
                else:
                    st.markdown(f"• Grounding risk: **Will ground** (depth {depth:.0f} ft, draft {draft:.0f} ft, deficit {ukc:.0f} ft)")

                st.markdown("")

                # Impact Assessment (only if won't ground)
                if not analysis['will_ground']:
                    st.markdown("**Impact Assessment** *(if collision occurs)*")
                    st.markdown(f"• Vessel demand: {analysis['impact_force_kips']:,.0f} kips *(at current speed)*")
                    st.markdown(f"• Pier lateral capacity: {analysis['pier_lateral_capacity_kips']:,} kips *(pending structural analysis)*")
                    st.markdown(f"• Demand/Capacity ratio: {analysis['dc_ratio']:.2f}")

                    # Can endanger bridge?
                    if analysis['dc_ratio'] >= 1.0:
                        st.markdown(f"• **Can endanger bridge at current speed?** ⚠️ **YES** (impact exceeds pier capacity)")
                    else:
                        st.markdown(f"• **Can endanger bridge at current speed?** ✓ No (impact within pier capacity)")
                else:
                    st.markdown("**Impact Assessment**")
                    st.markdown("• Vessel will ground before reaching pier - no collision possible")
    else:
        st.info("No vessels detected in monitoring area")

    # Bridge Information Section
    st.markdown("---")
    st.subheader("🌉 Bridge Information")
    with st.expander("View Details", expanded=False):
        st.markdown("### Basic Identification")
        st.markdown("""
        • **Name:** Maurice J. Tobin Memorial Bridge (Tobin Bridge)
        • **Location:** Boston/Chelsea, Massachusetts (42.385°N, 71.048°W)
        • **Year Built:** 1950
        • **Owner:** Massachusetts Port Authority (Massport)
        • **Bridge Type:** Cantilever truss bridge
        """)

        st.markdown("### Physical Characteristics")
        st.markdown("""
        • **Main Span Length:** 800 feet
        • **Total Bridge Length:** 2.57 miles (including approaches)
        • **Vertical Clearance:** 135 feet MHW
        • **Horizontal Clearance:** 800 feet (main span)
        • **Number of Piers:** 3 (water piers)
        """)

        st.markdown("### Traffic & Importance")
        st.markdown("""
        • **Average Daily Traffic:** ~80,000 vehicles
        • **Connects:** Boston (Charlestown) to Chelsea
        • **Route:** US Route 1
        • **Toll Bridge:** Yes (northbound only)
        """)

        st.markdown("### Structural Condition")
        st.markdown("""
        • **Deck Condition Rating:** [NBI] (0-9 scale, 9=excellent)
        • **Superstructure Rating:** [NBI] (0-9 scale)
        • **Substructure Rating:** [NBI] (0-9 scale)
        • **Last Inspection:** [NBI]
        """)

        st.markdown("### Safety Context")
        st.markdown("""
        • **NTSB High-Risk Bridge:** Yes (Safety Recommendation 24-016)
        • **Risk Factor:** Vessel collision vulnerability
        • **Required Mitigation:** Vessel detection + motorist warning system
        """)

        st.markdown("---")
        st.markdown("*📊 Data source: FHWA National Bridge Inventory (NBI)*")

    # Maritime Navigation Data Section
    st.subheader("⚓ Maritime Navigation Data")
    with st.expander("View Details", expanded=False):
        st.markdown("### Navigation Channel")
        st.markdown("""
        • **Chart Reference:** NOAA Chart 13272 (Boston Inner Harbor)
        • **Channel:** Mystic River / Chelsea Creek
        • **Maintained Depth:** 35 feet MLW
        • **Project Depth:** 35 feet
        """)

        st.markdown("### Clearances")
        st.markdown("""
        • **Vertical Clearance:** 135 feet MHW (Mean High Water)
        • **Horizontal Clearance:** 800 feet (main span)
        """)

        st.markdown("### Currents & Tides")
        st.markdown("""
        • **Maximum Current:** ~1-2 knots (ebb/flood)
        • **Tidal Range:** ~9-10 feet (Mean Range)
        • **Current Pattern:** Tidal flow in Mystic River
        """)

        st.markdown("### Vessel Traffic")
        st.markdown("""
        • **Typical Vessels:** Tankers, tugs, barges, fishing vessels
        • **Terminal Traffic:** Chelsea fuel terminals
        • **VTS Coverage:** Coast Guard Sector Boston
        """)

        st.markdown("### Pier-Specific Data")
        st.markdown("""
        • **Number of Water Piers:** 3
        • **Pier 1 Location:** Southern pier
        • **Pier 2 Location:** Central pier
        • **Pier 3 Location:** Northern pier
        • **Water Depth at Piers:** ~35 feet
        • **Pier Lateral Capacity:** 5,000 kips [PLACEHOLDER - requires structural analysis]
        """)

        st.markdown("### Protection Systems")
        st.markdown("""
        • **Current Systems:** [PLACEHOLDER - survey required]
        • **Proposed Systems:** AIS monitoring + Computer vision detection
        """)

        st.markdown("---")
        st.markdown("""
        *📊 Data sources:*
        - *Navigation: NOAA Nautical Chart 13272*
        - *Pier capacity: Placeholder - requires structural engineering analysis*
        - *Pier coordinates: GPS coordinates provided*

        *Production deployments include site-specific data from bridge owner:
        structural design documents, as-built drawings, protection system inventory,
        and emergency response protocols.*
        """)

# Footer
st.markdown("---")

st.markdown("""
**Engineering Notes:**
- Impact forces calculated per AASHTO Guide Specifications
- Lateral pier capacity: 5,000 kips (placeholder pending structural analysis)
- Grounding threshold: 10 ft clearance deficit

**Trajectory Projections:**
- Current implementation: Straight-line projection based on vessel speed and course
- Does not currently account for: tidal currents, wind effects, or vessel-specific maneuverability characteristics
- Future enhancements: Integration with NOAA tidal current data, vessel maneuverability models based on size/type, and real-time weather corrections

**About Roebling Labs:** We protect bridge users from vessel collision using real-time transponder (AIS) tracking and computer vision.

We combine vessel trajectory forecasting with AASHTO bridge impact analysis to continuously assign a threat level to each vessel within 30 nautical miles of the site.

Learn more at [roeblinglabs.com](https://roeblinglabs.com)
""")

st.markdown("---")
st.markdown("### 🚦 Threat Category Definitions")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("""
    **🔴 ALARM - Close Bridge Immediately**
    - Vessel demand/capacity ratio ≥ 1.0
    - Excessive speed (>15 knots) approaching bridge
    - Distance < 2 nautical miles
    - **Action Required:** Activate bridge closure protocol
    - **Note:** Off-course detection requires site-specific navigation channel mapping (future enhancement)

    **🟠 ELEVATED MONITORING - Heightened Awareness**
    - Large vessel (D/C ≥ 0.75) within 5 nm
    - Approaching bridge
    - **Normal for vessels transiting under bridge**
    - Routine monitoring protocols apply
    """)

with col_b:
    st.markdown("""
    **🟡 MONITOR - Routine Tracking**
    - Large vessel (D/C ≥ 0.5) within 10 nm
    - Not in immediate approach
    - Standard monitoring procedures

    **🟢 NEGLIGIBLE THREAT - Safe Passage**
    - Small vessels (D/C < 0.5)
    - Vessels heading away from bridge
    - Vessels that will ground before pier
    - Stationary vessels or far from bridge (>10 nm)
    - No action required
    """)
