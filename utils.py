import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from datetime import datetime, date, timedelta
from google.cloud import bigquery
import uuid


# Function to get BigQuery credentials
def get_credentials():
    """Get BigQuery credentials from secrets or service account file"""
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
            st.error("No credentials found for BigQuery access")
            return None
    return credentials


# Function to load car location data
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_car_locations():
    """Load current car locations from BigQuery"""
    try:
        credentials = get_credentials()
        if not credentials:
            return pd.DataFrame()

        client = bigquery.Client(credentials=credentials)

        query = """
        SELECT car_name, location_stage_name
        FROM reporting.daily_car_status 
        WHERE vehicle_allocation_category = "Wholesale" 
        AND date_key = CURRENT_DATE()
        ORDER BY car_name
        """

        car_locations = client.query(query).to_dataframe()
        return car_locations

    except Exception as e:
        st.error(f"Error loading car locations: {str(e)}")
        return pd.DataFrame()


# Function to load movement queue status
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_movement_queue():
    """Load movement queue status for in-progress requests"""
    try:
        credentials = get_credentials()
        if not credentials:
            return pd.DataFrame()

        client = bigquery.Client(credentials=credentials)

        query = """
        SELECT 
            Vehicle_Request_Id, 
            dealer_name, 
            car_name, 
            request_type, 
            FORMAT_DATE('%d/%m/%Y', DATE(vehicle_request_created_at)) AS request_created_date, 
            contacted_at, 
            contacted_user, 
            request_status, 
            failure_reason, 
            other_failure_reasons, 
            buy_now_type,
            CASE  
                WHEN contacted_user IS NULL AND request_status != 'received' THEN 'Passed the contacted stage' 
                WHEN contacted_user IS NULL AND request_status = 'received' THEN 'Received' 
                WHEN contacted_user IS NOT NULL THEN 'Contacted' 
                ELSE 'Unknown' 
            END AS request_progress,
            -- SLA calculations (simplified for display)
            CASE  
                WHEN contacted_at IS NOT NULL THEN 
                    TIMESTAMP_DIFF(contacted_at, vehicle_request_created_at, MINUTE)
                ELSE NULL 
            END AS SLA_minutes
        FROM ajans_dealers.dealer_requests 
        WHERE request_status = 'Inprogress'
        AND DATE(vehicle_request_created_at) >= '2025-01-01' 
        ORDER BY vehicle_request_created_at DESC
        """

        movement_queue = client.query(query).to_dataframe()
        return movement_queue

    except Exception as e:
        st.error(f"Error loading movement queue: {str(e)}")
        return pd.DataFrame()


# Function to load dealers for dropdown
@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_dealers():
    """Load dealer data from BigQuery"""
    try:
        credentials = get_credentials()
        if not credentials:
            return []

        client = bigquery.Client(credentials=credentials)

        query = """
        SELECT DISTINCT dealer_code, dealer_name
        FROM `pricing-338819.ajans_dealers.dealers`
        WHERE dealer_code IS NOT NULL AND dealer_name IS NOT NULL
        ORDER BY dealer_name
        """

        dealers_data = client.query(query).to_dataframe()
        return dealers_data.to_dict('records')

    except Exception as e:
        st.error(f"Error loading dealers: {str(e)}")
        return []


# Function to load car names
@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_car_names():
    """Load car names from BigQuery"""
    try:
        credentials = get_credentials()
        if not credentials:
            return []

        client = bigquery.Client(credentials=credentials)

        query = """
        SELECT DISTINCT car_name
        FROM reporting.vehicle_acquisition_to_selling
        WHERE allocation_category = "Wholesale" 
        AND current_status IN ("Published", "Being Sold")
        ORDER BY 1
        """

        cars_data = client.query(query).to_dataframe()
        return cars_data['car_name'].tolist()

    except Exception as e:
        st.error(f"Error loading car names: {str(e)}")
        return []


# Function to open a new visit
def open_visit(visit_data):
    """Open a new visit request in BigQuery"""
    try:
        credentials = get_credentials()
        if not credentials:
            return False, "Error: No credentials found"

        client = bigquery.Client(credentials=credentials)

        query = """
        INSERT INTO `pricing-338819.wholesale_test.pre_visit_confirmation`
        (id, c_name, request_id, dealer_name, dealer_phone_number, visit_date, 
         time_slot, car_location, agent_name, status, notes, opened_by, opened_at, created_at)
        VALUES
        (@id, @c_name, @request_id, @dealer_name, @dealer_phone_number, @visit_date,
         @time_slot, @car_location, @agent_name, @status, @notes, @opened_by, @opened_at, @created_at)
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id", "STRING", visit_data['id']),
                bigquery.ScalarQueryParameter("c_name", "STRING", visit_data['c_name']),
                bigquery.ScalarQueryParameter("request_id", "STRING", visit_data['request_id']),
                bigquery.ScalarQueryParameter("dealer_name", "STRING", visit_data['dealer_name']),
                bigquery.ScalarQueryParameter("dealer_phone_number", "STRING", visit_data['dealer_phone_number']),
                bigquery.ScalarQueryParameter("visit_date", "DATE", visit_data['visit_date']),
                bigquery.ScalarQueryParameter("time_slot", "STRING", visit_data['time_slot']),
                bigquery.ScalarQueryParameter("car_location", "STRING", visit_data['car_location']),
                bigquery.ScalarQueryParameter("agent_name", "STRING", visit_data['agent_name']),
                bigquery.ScalarQueryParameter("status", "STRING", visit_data['status']),
                bigquery.ScalarQueryParameter("notes", "STRING", visit_data['notes']),
                bigquery.ScalarQueryParameter("opened_by", "STRING", visit_data['opened_by']),
                bigquery.ScalarQueryParameter("opened_at", "TIMESTAMP", visit_data['opened_at']),
                bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", visit_data['created_at'])
            ]
        )

        query_job = client.query(query, job_config=job_config)
        query_job.result()

        return True, "Visit opened successfully!"

    except Exception as e:
        return False, f"Error opening visit: {str(e)}"


# Function to confirm a visit
def confirm_visit(visit_id, confirmed_by, notes=None):
    """Confirm an open visit in BigQuery"""
    try:
        credentials = get_credentials()
        if not credentials:
            return False, "Error: No credentials found"

        client = bigquery.Client(credentials=credentials)

        query = """
        UPDATE `pricing-338819.wholesale_test.pre_visit_confirmation`
        SET status = 'confirmed', 
            confirmed_by = @confirmed_by, 
            confirmed_at = @confirmed_at,
            updated_at = @updated_at,
            notes = CASE 
                WHEN @notes IS NOT NULL THEN 
                    CASE 
                        WHEN notes IS NULL THEN @notes
                        ELSE CONCAT(notes, @separator, @notes)
                    END
                ELSE notes
            END
        WHERE id = @visit_id AND status = 'open'
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("visit_id", "STRING", visit_id),
                bigquery.ScalarQueryParameter("confirmed_by", "STRING", confirmed_by),
                bigquery.ScalarQueryParameter("confirmed_at", "TIMESTAMP", datetime.now()),
                bigquery.ScalarQueryParameter("updated_at", "TIMESTAMP", datetime.now()),
                bigquery.ScalarQueryParameter("notes", "STRING", notes),
                bigquery.ScalarQueryParameter("separator", "STRING", "\n--- Confirmation Notes ---\n")
            ]
        )

        query_job = client.query(query, job_config=job_config)
        result = query_job.result()

        # Check if any rows were updated
        if query_job.num_dml_affected_rows > 0:
            return True, "Visit confirmed successfully!"
        else:
            return False, "Visit not found or already confirmed"

    except Exception as e:
        return False, f"Error confirming visit: {str(e)}"


# Function to cancel a visit
def cancel_visit(visit_id, cancelled_by, notes=None):
    """Cancel a visit in BigQuery"""
    try:
        credentials = get_credentials()
        if not credentials:
            return False, "Error: No credentials found"

        client = bigquery.Client(credentials=credentials)

        query = """
        UPDATE `pricing-338819.wholesale_test.pre_visit_confirmation`
        SET status = 'cancelled', 
            updated_at = @updated_at,
            notes = CASE 
                WHEN @notes IS NOT NULL THEN 
                    CASE 
                        WHEN notes IS NULL THEN @notes
                        ELSE CONCAT(notes, @separator, @notes)
                    END
                ELSE notes
            END
        WHERE id = @visit_id AND status IN ('open', 'confirmed')
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("visit_id", "STRING", visit_id),
                bigquery.ScalarQueryParameter("updated_at", "TIMESTAMP", datetime.now()),
                bigquery.ScalarQueryParameter("notes", "STRING", notes),
                bigquery.ScalarQueryParameter("separator", "STRING", f"\n--- Cancelled by {cancelled_by} ---\n")
            ]
        )

        query_job = client.query(query, job_config=job_config)
        result = query_job.result()

        # Check if any rows were updated
        if query_job.num_dml_affected_rows > 0:
            return True, "Visit cancelled successfully!"
        else:
            return False, "Visit not found or already cancelled"

    except Exception as e:
        return False, f"Error cancelling visit: {str(e)}"


# Function to load open and confirmed visits
@st.cache_data(ttl=30)  # Cache for 30 seconds for more frequent updates
def load_open_visits():
    """Load open and confirmed visits from BigQuery"""
    try:
        credentials = get_credentials()
        if not credentials:
            return pd.DataFrame()

        client = bigquery.Client(credentials=credentials)

        query = """
        SELECT 
            id,
            c_name,
            request_id,
            dealer_name,
            dealer_phone_number,
            visit_date,
            time_slot,
            car_location,
            agent_name,
            status,
            notes,
            opened_by,
            opened_at,
            confirmed_by,
            confirmed_at
        FROM `pricing-338819.wholesale_test.pre_visit_confirmation`
        WHERE status = 'open' 
           OR (status = 'confirmed')
        ORDER BY opened_at DESC
        """

        open_visits = client.query(query).to_dataframe()
        return open_visits

    except Exception as e:
        st.error(f"Error loading open visits: {str(e)}")
        return pd.DataFrame()
