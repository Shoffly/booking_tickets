import streamlit as st
import uuid
from datetime import datetime, date, timedelta
from utils import (
    load_car_locations, load_dealers, load_car_names, open_visit
)

# Set page config
st.set_page_config(
    page_title="Open New Visit",
    page_icon="🆕",
    layout="wide"
)

st.title("🆕 Open New Visit Request")

# Load initial data
with st.spinner("Loading data..."):
    car_locations_df = load_car_locations()
    dealers_list = load_dealers()
    car_names_list = load_car_names()

# Generate unique ID
visit_id = str(uuid.uuid4())

# Car selection outside the form for dynamic location updates
if car_names_list:
    selected_car = st.selectbox(
        "Car Name (C-name) *",
        options=car_names_list,
        help="Select the car for the visit",
        key="car_name_selection"
    )
else:
    selected_car = st.text_input("Car Name (C-name) *",
                                 help="Enter the car name manually",
                                 key="car_name_input")

# Show car location dynamically when car selection changes
if selected_car and not car_locations_df.empty:
    car_location_info = car_locations_df[car_locations_df['car_name'] == selected_car]
    if not car_location_info.empty:
        location = car_location_info.iloc[0]['location_stage_name']
        st.info(f"🚗 Car Location: **{location}**")
    else:
        st.warning("⚠️ Car location not found in current data")
        location = "Unknown"
elif selected_car:
    st.warning("⚠️ Car location not found in current data")
    location = "Unknown"
else:
    location = "Unknown"

with st.form("open_visit_form"):
    st.info(f"Visit ID: {visit_id}")

    col1, col2 = st.columns(2)

    with col1:
        # Request ID (optional)
        request_id = st.text_input(
            "Request ID",
            help="Enter the request ID if available"
        )

        # Dealer Name
        if dealers_list:
            dealer_options = [(dealer['dealer_name'], f"{dealer['dealer_name']} ({dealer['dealer_code']})")
                              for dealer in dealers_list]
            dealer_names = [name for name, _ in dealer_options]
            dealer_displays = [display for _, display in dealer_options]

            selected_dealer_index = st.selectbox(
                "Dealer Name (D-name) *",
                options=range(len(dealer_options)),
                format_func=lambda i: dealer_displays[i],
                help="Select the dealer"
            )
            selected_dealer_name = dealer_names[selected_dealer_index]
        else:
            selected_dealer_name = st.text_input("Dealer Name (D-name) *",
                                                 help="Enter dealer name manually")

        # Agent name
        agent_name = st.text_input("Agent Name *",
                                   help="Enter your name")

    with col2:
        # Dealer Phone Number
        dealer_phone = st.text_input(
            "Dealer Phone Number *",
            help="Enter the dealer's phone number"
        )

        # Visit Date
        min_date = date.today()
        max_date = date.today() + timedelta(days=30)
        visit_date = st.date_input(
            "Proposed Visit Date *",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            help="Select the proposed visit date"
        )

        # Time Slot
        time_slots = [
            "09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00",
            "12:00 - 13:00", "13:00 - 14:00", "14:00 - 15:00",
            "15:00 - 16:00", "16:00 - 17:00"
        ]
        selected_time_slot = st.selectbox(
            "Proposed Time Slot *",
            options=time_slots,
            help="Select the proposed time slot for the visit"
        )

    # Notes
    notes = st.text_area(
        "Initial Notes",
        help="Add any initial notes or special requirements",
        height=100
    )

    # Submit button
    submit_button = st.form_submit_button("🆕 Open Visit Request", use_container_width=True)

    if submit_button:
        # Validation
        if not selected_car:
            st.error("Please select a car name")
        elif not selected_dealer_name:
            st.error("Please select a dealer name")
        elif not dealer_phone:
            st.error("Please enter dealer phone number")
        elif not agent_name:
            st.error("Please enter your agent name")
        else:
            # Prepare visit data
            visit_data = {
                'id': visit_id,
                'c_name': selected_car,
                'request_id': request_id if request_id else None,
                'dealer_name': selected_dealer_name,
                'dealer_phone_number': dealer_phone,
                'visit_date': visit_date,
                'time_slot': selected_time_slot,
                'car_location': location,
                'agent_name': agent_name,
                'status': 'open',  # Always open status
                'notes': notes if notes else None,
                'opened_by': agent_name,
                'opened_at': datetime.now(),
                'created_at': datetime.now()
            }

            # Submit data
            success, message = open_visit(visit_data)

            if success:
                st.success(message)
                st.balloons()

                # Clear cache to refresh open visits in other pages
                st.cache_data.clear()

                # Show visit details
                with st.expander("📋 Visit Request Details"):
                    st.json({
                        "Visit ID": visit_data['id'],
                        "Car Name": visit_data['c_name'],
                        "Dealer": visit_data['dealer_name'],
                        "Phone": visit_data['dealer_phone_number'],
                        "Proposed Visit Date": str(visit_data['visit_date']),
                        "Proposed Time Slot": visit_data['time_slot'],
                        "Status": "🟡 OPEN (Awaiting Confirmation)",
                        "Opened By": visit_data['opened_by'],
                        "Car Location": location
                    })
                    
                # Add navigation hint
                st.info("💡 **Next Step:** Go to the 'Manage Visits' page to confirm or manage this visit request.")
                
            else:
                st.error(message)