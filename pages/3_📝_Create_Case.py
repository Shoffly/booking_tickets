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


# Get BigQuery client
def get_bigquery_client():
    """Get BigQuery client with credentials"""
    try:
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
                return None

        if credentials:
            return bigquery.Client(credentials=credentials)
        return None
    except Exception as e:
        st.error(f"Error connecting to database: {str(e)}")
        return None

# Load data function (cache only the data, not the client)
@st.cache_data(ttl=43200)  # Cache data for 12 hours
def load_case_data():
    """Load necessary data for case creation"""
    client = get_bigquery_client()
    if not client:
        return None, None
        
    try:
        # Load dealer data
        dealer_query = """
        SELECT DISTINCT dealer_code, dealer_name
        FROM `pricing-338819.ajans_dealers.dealer_full_segmentation`
        WHERE dealer_code IS NOT NULL AND dealer_name IS NOT NULL
        ORDER BY dealer_name
        """

        # Load car data from the actual live cars query (simplified version)
        car_query = """
        with publishing AS (
        SELECT sf_vehicle_name,
               publishing_state,
               days_on_app AS DOA,
               MAX(published_at) over (partition by sf_vehicle_name) AS max_publish_date
        FROM ajans_dealers.ajans_wholesale_to_retail_publishing_logs
        WHERE sf_vehicle_name NOT in ("C-32211","C-32203") 
        QUALIFY published_at = max_publish_date
        ),

        live_cars AS (
        SELECT sf_vehicle_name,
               type AS live_status
        FROM reporting.ajans_vehicle_history 
        WHERE date_key = current_date() ),

        car_info AS (
        with max_date AS (
        SELECT sf_vehicle_name,
               make,
               model,
               year,
               row_number()over(PARTITION BY sf_vehicle_name ORDER BY event_date DESC) AS row_number
        FROM ajans_dealers.vehicle_activity )

        SELECT sf_vehicle_name, make, model, year
        FROM max_date WHERE row_number = 1 )

        SELECT DISTINCT publishing.sf_vehicle_name,
               CONCAT(car_info.make, ' ', car_info.model, ' (', CAST(car_info.year AS STRING), ') - ', publishing.sf_vehicle_name) as display_name
        FROM publishing
        LEFT JOIN live_cars ON publishing.sf_vehicle_name = live_cars.sf_vehicle_name
        LEFT JOIN car_info ON publishing.sf_vehicle_name = car_info.sf_vehicle_name 
        LEFT JOIN reporting.vehicle_acquisition_to_selling a ON publishing.sf_vehicle_name = a.car_name
        WHERE a.allocation_category = "Wholesale" AND a.current_status in ("Published" , "Being Sold")
        ORDER BY display_name
        """

        try:
            dealer_results = client.query(dealer_query).result()
            car_results = client.query(car_query).result()

            dealers = [{"dealer_code": row.dealer_code, "dealer_name": row.dealer_name} 
                      for row in dealer_results]
            cars = [{"sf_vehicle_name": row.sf_vehicle_name, "display_name": row.display_name} 
                   for row in car_results]

            return dealers, cars
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return None, None

    except Exception as e:
        st.error(f"Error querying database: {str(e)}")
        return None, None


# Load data
with st.spinner("Loading data..."):
    dealers, cars = load_case_data()

if dealers is None or cars is None:
    st.error("Unable to load data. Please check your database connection and credentials.")
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
        car_choices = [""] + [car["display_name"] for car in cars] if cars else [""]
        selected_car_display = st.selectbox("Car (Optional)", car_choices)

    # Case details text area
    details = st.text_area("Case Details *", height=150,
                           help="Provide detailed information about the case")

    # Extract dealer_code from selection
    dealer_code = selected_dealer.split(" - ")[0] if selected_dealer else None
    
    # Extract car_code from selection
    car_code = None
    if selected_car_display and cars:
        for car in cars:
            if car["display_name"] == selected_car_display:
                car_code = car["sf_vehicle_name"]
                break

    # Submit button
    submit_button = st.form_submit_button("Create Case", use_container_width=True)

    if submit_button:
        if not details.strip():
            st.error("Please enter case details")
        else:
            try:
                # Get a fresh client for submission
                client = get_bigquery_client()
                if not client:
                    st.error("Unable to connect to the database. Please check your credentials.")
                    st.stop()
                
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
                        "Car": selected_car_display if selected_car_display else "Not specified",
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

