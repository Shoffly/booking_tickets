import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import load_open_visits, confirm_visit, cancel_visit

# Set page config
st.set_page_config(
    page_title="Manage Visits",
    page_icon="✅",
    layout="wide"
)

st.title("✅ Manage Visits")

# Check if we need to refresh visits data
if st.session_state.get('refresh_visits', False):
    st.cache_data.clear()
    st.session_state['refresh_visits'] = False

# Load open visits
open_visits_df = load_open_visits()

# Add refresh button and auto-refresh info
col_refresh, col_info, col_empty = st.columns([1, 2, 2])
with col_refresh:
    if st.button("🔄 Refresh", help="Refresh visit data"):
        st.cache_data.clear()
        st.rerun()
with col_info:
    st.caption(f"🔄 Auto-refreshes every 30 seconds")
    if not open_visits_df.empty:
        st.caption(f"📊 Data loaded: {datetime.now().strftime('%H:%M:%S')}")

if not open_visits_df.empty:
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_visits = len(open_visits_df)
        st.metric("Total Visits", total_visits)
    with col2:
        open_count = len(open_visits_df[open_visits_df['status'] == 'open'])
        st.metric("Open Visits", open_count)
    with col3:
        confirmed_count = len(open_visits_df[open_visits_df['status'] == 'confirmed'])
        st.metric("Confirmed Visits", confirmed_count)
    with col4:
        today_visits = len(open_visits_df[pd.to_datetime(open_visits_df['visit_date']).dt.date == date.today()])
        st.metric("Today's Visits", today_visits)

    st.divider()

    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        dealer_filter = st.selectbox(
            "Filter by Dealer:",
            options=["All"] + list(open_visits_df['dealer_name'].unique()),
            key="open_visits_dealer_filter"
        )
    with col2:
        date_filter = st.selectbox(
            "Filter by Visit Date:",
            options=["All"] + [str(d) for d in
                               sorted(pd.to_datetime(open_visits_df['visit_date']).dt.date.unique())],
            key="open_visits_date_filter"
        )

    # Apply filters
    filtered_visits = open_visits_df.copy()
    if dealer_filter != "All":
        filtered_visits = filtered_visits[filtered_visits['dealer_name'] == dealer_filter]
    if date_filter != "All":
        filtered_visits = filtered_visits[
            pd.to_datetime(filtered_visits['visit_date']).dt.date == pd.to_datetime(date_filter).date()]

    st.subheader(f"📋 Active Visits ({len(filtered_visits)})")

    # Display each visit with action buttons
    for idx, visit in filtered_visits.iterrows():
        status_emoji = "🟡" if visit['status'] == 'open' else "🟢"
        status_text = visit['status'].upper()
        with st.expander(
                f"{status_emoji} {visit['c_name']} - {visit['dealer_name']} - {visit['visit_date']} {visit['time_slot']} [{status_text}]",
                expanded=False
        ):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.write(f"**Visit ID:** {visit['id']}")
                st.write(f"**Car:** {visit['c_name']}")
                st.write(f"**Dealer:** {visit['dealer_name']}")
                st.write(f"**Phone:** {visit['dealer_phone_number']}")
                st.write(f"**Visit Date:** {visit['visit_date']}")
                st.write(f"**Time Slot:** {visit['time_slot']}")
                st.write(f"**Car Location:** {visit['car_location'] or 'Unknown'}")
                st.write(f"**Opened By:** {visit['opened_by']}")
                st.write(f"**Opened At:** {pd.to_datetime(visit['opened_at']).strftime('%Y-%m-%d %H:%M')}")
                if visit['notes']:
                    st.write(f"**Notes:** {visit['notes']}")

            with col2:
                # Visit status and confirmation info
                if visit['status'] == 'confirmed':
                    st.write("**Status:** ✅ CONFIRMED")
                    if visit['confirmed_by']:
                        st.write(f"**Confirmed By:** {visit['confirmed_by']}")
                    if visit['confirmed_at']:
                        confirmed_time = pd.to_datetime(visit['confirmed_at']).strftime('%Y-%m-%d %H:%M')
                        st.write(f"**Confirmed At:** {confirmed_time}")
                else:
                    st.write("**Status:** 🟡 OPEN")
                    st.write("*Awaiting confirmation*")

            with col3:
                # Action buttons - simplified to only Confirm and Cancel
                st.write("**Actions**")

                # Show confirm button only for open visits
                if visit['status'] == 'open':
                    if st.button("✅ Confirm Visit", key=f"confirm_btn_{visit['id']}", use_container_width=True):
                        st.session_state[f"show_confirm_modal_{visit['id']}"] = True

                # Show cancel button for both open and confirmed visits
                if st.button("❌ Cancel Visit", key=f"cancel_btn_{visit['id']}", use_container_width=True):
                    st.session_state[f"show_cancel_modal_{visit['id']}"] = True

                # Confirm modal
                if st.session_state.get(f"show_confirm_modal_{visit['id']}", False):
                    with st.container():
                        st.markdown("---")
                        st.markdown("### ✅ Confirm Visit")

                        confirming_agent = st.text_input(
                            "Your Name:",
                            key=f"modal_confirm_agent_{visit['id']}",
                            help="Enter your name as the confirming agent"
                        )
                        confirmation_notes = st.text_area(
                            "Confirmation Notes:",
                            key=f"modal_confirm_notes_{visit['id']}",
                            help="Add any confirmation notes",
                            height=80
                        )

                        col_confirm1, col_confirm2 = st.columns(2)
                        with col_confirm1:
                            if st.button("✅ Confirm", key=f"do_confirm_{visit['id']}",
                                         use_container_width=True):
                                if not confirming_agent:
                                    st.error("Please enter your name")
                                else:
                                    success, message = confirm_visit(
                                        visit['id'],
                                        confirming_agent,
                                        confirmation_notes if confirmation_notes else None
                                    )

                                    if success:
                                        st.success(message)
                                        st.session_state[f"show_confirm_modal_{visit['id']}"] = False
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(message)

                        with col_confirm2:
                            if st.button("🚫 Cancel", key=f"cancel_confirm_{visit['id']}",
                                         use_container_width=True):
                                st.session_state[f"show_confirm_modal_{visit['id']}"] = False
                                st.rerun()

                # Cancel modal
                if st.session_state.get(f"show_cancel_modal_{visit['id']}", False):
                    with st.container():
                        st.markdown("---")
                        st.markdown("### ❌ Cancel Visit")

                        cancelling_agent = st.text_input(
                            "Your Name:",
                            key=f"modal_cancel_agent_{visit['id']}",
                            help="Enter your name"
                        )
                        cancel_reasons = [
                            "Car Sold",
                            "Being Sold",
                            "Dealer Not Eligible",
                            "Had a claint changed his mind",
                            "Wrong Car Selected",
                            "Reallocated to Retail",
                            "Queue Abandoned",
                            "Dealer not reached (Handling)",
                            "Had a clint and changed his mind",
                            "Dealer refused to wait",
                            "Wrong Request Submited",
                            "Car under maintenance"
                        ]
                        cancel_reason = st.selectbox(
                            "Cancel Reason:",
                            options=[""] + cancel_reasons,
                            key=f"modal_cancel_reason_{visit['id']}",
                            help="Select the reason for cancelling this visit"
                        )

                        col_cancel1, col_cancel2 = st.columns(2)
                        with col_cancel1:
                            if st.button("❌ Cancel Visit", key=f"do_cancel_{visit['id']}",
                                         use_container_width=True):
                                if not cancelling_agent:
                                    st.error("Please enter your name")
                                else:
                                    success, message = cancel_visit(
                                        visit['id'],
                                        cancelling_agent,
                                        cancel_reason if cancel_reason else None
                                    )

                                    if success:
                                        st.success(message)
                                        st.session_state[f"show_cancel_modal_{visit['id']}"] = False
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(message)

                        with col_cancel2:
                            if st.button("🚫 Don't Cancel", key=f"cancel_cancel_{visit['id']}",
                                         use_container_width=True):
                                st.session_state[f"show_cancel_modal_{visit['id']}"] = False
                                st.rerun()
else:
    st.info("🎉 No active visits! All visits have been completed/cancelled or there are no visits yet.")
    st.write("Use the 'Home' page to create new visit requests.")
