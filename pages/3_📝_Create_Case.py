import streamlit as st
import uuid
from datetime import datetime
import secrets
from google.cloud import bigquery
from google.oauth2 import service_account


# Set page config
st.set_page_config(
    page_title="Create Case",
    page_icon="📝",
    layout="wide"
)

st.title("📝 Create New Case")

# Check if user is authenticated (assuming similar auth pattern as other pages)
if "current_user" not in st.session_state:
    st.error("Please log in to access this page")
    st.stop()




# Load data function (simplified version - you may need to import from utils)
@st.cache_data(ttl=43200)  # Cache data for 12 hours
def load_case_data():
    """Load necessary data for case creation"""
    try:
        # Get credentials
        credentials = None
        try:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["service_account"]
            )
        except (KeyError, FileNotFoundError):
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    'service_account.json'
                )
            except FileNotFoundError:
                return None, None, None

        if credentials:
            client = bigquery.Client(credentials=credentials)

            # Load dealer data
            dealer_query = """
            SELECT DISTINCT dealer_code, dealer_name
            FROM `pricing-338819.wholesale_test.dealer_segmentation`
            WHERE dealer_code IS NOT NULL AND dealer_name IS NOT NULL
            ORDER BY dealer_name
            """

            # Load car data
            car_query = """
            SELECT DISTINCT sf_vehicle_name
            FROM `pricing-338819.wholesale_test.live_cars`
            WHERE sf_vehicle_name IS NOT NULL
            ORDER BY sf_vehicle_name
            """

            try:
                dealer_results = client.query(dealer_query).result()
                car_results = client.query(car_query).result()

                dealers = [{"dealer_code": row.dealer_code, "dealer_name": row.dealer_name}
                           for row in dealer_results]
                cars = [row.sf_vehicle_name for row in car_results]

                return dealers, cars, client
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
                return None, None, None

    except Exception as e:
        st.error(f"Error connecting to database: {str(e)}")
        return None, None, None


# Load data
with st.spinner("Loading data..."):
    dealers, cars, client = load_case_data()

if client is None:
    st.error("Unable to connect to the database. Please check your credentials.")
    st.stop()

# Predefined buckets
buckets = [
    "Technical Issue",
    "Payment Problem",
    "Account Access",
    "App Navigation",
    "Dealer Complaint",
    "Feature Request",
    "Data Discrepancy",
    "Other"
]

# Predefined departments
departments = [
    "Marketplace",
    "Growth",
    "Product",
    "Ops",
    "Finance"
]

# Form for case creation
with st.form("create_case_form"):
    st.subheader("Case Information")

    col1, col2 = st.columns(2)

    with col1:
        # Case details
        selected_bucket = st.selectbox("Bucket *", buckets)
        department = st.selectbox("Accountable Department *", departments)

    with col2:
        # Optional dealer selection
        dealer_choices = [""] + [f"{dealer['dealer_code']} - {dealer['dealer_name']}"
                                 for dealer in dealers] if dealers else [""]
        selected_dealer = st.selectbox("Dealer (Optional)", dealer_choices)

        # Optional car selection
        car_choices = [""] + sorted(cars) if cars else [""]
        selected_car = st.selectbox("Car (Optional)", car_choices)

    # Case details text area
    details = st.text_area("Case Details *", height=150,
                           help="Provide detailed information about the case")

    # Extract dealer_code from selection
    dealer_code = selected_dealer.split(" - ")[0] if selected_dealer else None
    car_code = selected_car if selected_car else None

    # Submit button
    submit_button = st.form_submit_button("Create Case", use_container_width=True)

    if submit_button:
        if not details.strip():
            st.error("Please enter case details")
        else:
            try:
                # Generate a unique case ID
                case_id = f"CASE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"

                # Prepare the query
                query = """
                INSERT INTO `pricing-338819.wholesale_test.complaints`
                (case_id, bucket, details, submitted_by, status, submitted_at, accountable_department, dealer_code, car_code)
                VALUES
                (@case_id, @bucket, @details, @submitted_by, @status, @submitted_at, @department, @dealer_code, @car_code)
                """

                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("case_id", "STRING", case_id),
                        bigquery.ScalarQueryParameter("bucket", "STRING", selected_bucket),
                        bigquery.ScalarQueryParameter("details", "STRING", details),
                        bigquery.ScalarQueryParameter("submitted_by", "STRING",
                                                      st.session_state.get("current_user", "unknown")),
                        bigquery.ScalarQueryParameter("status", "STRING", "Open"),
                        bigquery.ScalarQueryParameter("submitted_at", "TIMESTAMP", datetime.now()),
                        bigquery.ScalarQueryParameter("department", "STRING", department),
                        bigquery.ScalarQueryParameter("dealer_code", "STRING",
                                                      dealer_code if dealer_code else None),
                        bigquery.ScalarQueryParameter("car_code", "STRING",
                                                      car_code if car_code else None),
                    ]
                )

                # Execute the query
                query_job = client.query(query, job_config=job_config)
                query_job.result()  # Wait for the query to complete

                st.success(f"✅ Case created successfully!")
                st.info(f"**Case ID:** {case_id}")

                # Show case summary
                with st.expander("📋 Case Summary"):
                    st.json({
                        "Case ID": case_id,
                        "Bucket": selected_bucket,
                        "Department": department,
                        "Submitted By": st.session_state.get("current_user", "unknown"),
                        "Status": "Open",
                        "Dealer": selected_dealer if selected_dealer else "Not specified",
                        "Car": selected_car if selected_car else "Not specified",
                        "Submitted At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })

                # Track case creation
                if "current_user" in st.session_state:
                    try:
                        posthog.capture(
                            st.session_state["current_user"],
                            'case_created',
                            {
                                'case_id': case_id,
                                'bucket': selected_bucket,
                                'department': department,
                                'timestamp': datetime.now().isoformat()
                            }
                        )
                    except Exception:
                        pass  # Ignore posthog errors

                # Clear the form by rerunning
                st.rerun()

            except Exception as e:
                st.error(f"Error creating case: {str(e)}")

# Add some helpful information
st.markdown("---")
st.markdown("### 💡 Tips for Creating Cases")
st.markdown("""
- **Be specific** in your case details to help the accountable department understand the issue
- **Include relevant context** such as error messages, steps to reproduce, or expected behavior
- **Select appropriate bucket** to ensure proper categorization and routing
- **Add dealer/car information** when relevant to provide additional context
""")
