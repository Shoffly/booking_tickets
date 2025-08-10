import streamlit as st
import pandas as pd
from utils import load_car_locations, load_movement_queue

# Set page config
st.set_page_config(
    page_title="Information Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Information Dashboard")

# Load data
with st.spinner("Loading data..."):
    car_locations_df = load_car_locations()
    movement_queue_df = load_movement_queue()

# Car Locations Section
st.subheader("🚗 Car Locations")
if not car_locations_df.empty:
    # Summary metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Cars", len(car_locations_df))
    with col2:
        unique_locations = len(car_locations_df['location_stage_name'].unique())
        st.metric("Unique Locations", unique_locations)

    # Location distribution
    location_counts = car_locations_df['location_stage_name'].value_counts()
    st.bar_chart(location_counts)

    # Searchable car locations
    search_car = st.text_input("Search for specific car:", key="car_search")
    if search_car:
        filtered_locations = car_locations_df[
            car_locations_df['car_name'].str.contains(search_car, case=False, na=False)
        ]
        st.dataframe(filtered_locations, use_container_width=True)
    else:
        st.dataframe(car_locations_df, use_container_width=True)
else:
    st.info("No car location data available")

st.divider()

# Movement Queue Section
st.subheader("🔄 Movement Queue Status (In-Progress)")
if not movement_queue_df.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("In-Progress Requests", len(movement_queue_df))
    with col2:
        contacted_count = len(movement_queue_df[movement_queue_df['contacted_user'].notna()])
        st.metric("Contacted Requests", contacted_count)
    with col3:
        avg_sla = movement_queue_df['SLA_minutes'].mean()
        if pd.notna(avg_sla):
            st.metric("Avg SLA (minutes)", f"{avg_sla:.1f}")
        else:
            st.metric("Avg SLA (minutes)", "N/A")

    # Filter by dealer
    unique_dealers = movement_queue_df['dealer_name'].unique()
    selected_dealer_filter = st.selectbox(
        "Filter by Dealer:",
        options=["All"] + list(unique_dealers),
        key="dealer_filter"
    )

    if selected_dealer_filter != "All":
        filtered_queue = movement_queue_df[movement_queue_df['dealer_name'] == selected_dealer_filter]
    else:
        filtered_queue = movement_queue_df

    st.dataframe(
        filtered_queue,
        column_config={
            "Vehicle_Request_Id": "Request ID",
            "dealer_name": "Dealer",
            "car_name": "Car",
            "request_type": "Type",
            "request_created_date": "Created",
            "request_progress": "Progress",
            "SLA_minutes": "SLA (min)"
        },
        use_container_width=True
    )
else:
    st.info("No in-progress movement requests found")
