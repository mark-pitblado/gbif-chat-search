import json
import openai
import requests
import streamlit as st
import pandas as pd
import os
import time
import random

from urllib.parse import urlencode
from dotenv import load_dotenv
from requests.exceptions import RequestException, Timeout, ConnectionError

# Set up API client

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("GBIF_CHAT_OPENAI_API_KEY"))
GBIF_API_BASE_URL = "https://api.gbif.org/v1/occurrence/search"

# Setup settings for app
st.set_page_config(
    page_title="GBIF Chat Search",
    page_icon="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0Ij48ZyBmaWxsPSIjMzE4NjJjIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGNsaXAtcnVsZT0iZXZlbm9kZCI+PHBhdGggZD0iTTIyLjU4NiAxMC4xNzNhMi4yNSAyLjI1IDAgMCAxLTIuMTc3LS41ODJsLS41NDEtLjU0MWE0Ljc1IDQuNzUgMCAwIDEtNS4xOS03LjM3MWE3LjcgNy43IDAgMCAwLTEuNjA0LS4zNzZBMTEgMTEgMCAwIDAgMTIgMS4yNUM2LjA2MyAxLjI1IDEuMjUgNi4wNjMgMS4yNSAxMmMwIDEuODU2LjQ3MSAzLjYwNSAxLjMgNS4xM2wtLjc4NyA0LjIzM2EuNzUuNzUgMCAwIDAgLjg3NC44NzRsNC4yMzMtLjc4OEExMC43IDEwLjcgMCAwIDAgMTIgMjIuNzVjNS45MzcgMCAxMC43NS00LjgxMyAxMC43NS0xMC43NXEwLS41NDMtLjA1My0xLjA3NHMtLjA0NS0uMzI1LS4xMTEtLjc1M00xOS45NyA1Ljk3YS43NS43NSAwIDAgMSAxLjA2IDBsMS41IDEuNWEuNzUuNzUgMCAwIDEtMS4wNiAxLjA2bC0xLjUtMS41YS43NS43NSAwIDAgMSAwLTEuMDYiLz48cGF0aCBkPSJNMTguNSAyLjc1YTEuNzUgMS43NSAwIDEgMCAwIDMuNWExLjc1IDEuNzUgMCAwIDAgMC0zLjVNMTUuMjUgNC41YTMuMjUgMy4yNSAwIDEgMSA2LjUgMGEzLjI1IDMuMjUgMCAwIDEtNi41IDAiLz48L2c+PC9zdmc+",
    layout="wide",
)


def extract_query_fields(user_input):
    system_prompt = """

    You are a chatbot helping users convert natural langauge prompts into Global Biodiversity Information FacilityAPI fields.

    Extract the taxonomy (scientific_name), location (locality), collection, institution, continent (continent), country (country), state/province (stateProvince), collector (recordedBy), collection date (eventDate), collector number (recordNumber), and mediaType from the user query:

    Return the result as a JSON dictionary using only valid gbif api parameters as keys if mentioned. For example, these are some examples of valid keys:
        'scientificName', 'locality', 'continent', 'country', 'stateProvince', 'recordedBy', 'eventDate', "recordNumber", "mediaType"

    Additional instructions:
        - Output should be valid JSON only.
        - Use 'location' only for geographic localities, lakes, cities, landmarks, etc. Do not put the collection or institution value in this field.
        - Only use recordedBy for human names.
        - The name of the collection, if present, should be assigned to the "collection" key in the JSON.
        - The name of the institution, if present, should be assigned to the "institution" key in the JSON.
        - If there is a range, separate the values by a ,
        - If there is a country specified, use the two letter code for that country in capital letters as the value.
        - If a continent is specified, use the following format "North America", "Europe". Do not capitlize it with an underscore.
        - If the user enters the common name for a scientific name, such as "Sparrow", use the scientific name that best fits that common name.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=1000,
    )
    extracted = response.choices[0].message.content
    return json.loads(extracted)


def get_institution_guid(institution_name: str) -> str:
    """
    Convert institution name to GBIF institution key (GUID).
    Returns the first match or None if no matches found.
    """
    if not institution_name or not institution_name.strip():
        return None

    search_url = (
        f"https://api.gbif.org/v1/grscicoll/institution/search?q={institution_name}"
    )
    try:
        response = make_request_with_retry(search_url, max_retries=2, base_delay=0.5)
        data = response.json()

        if data.get("results") and len(data["results"]) > 0:
            return data["results"][0]["key"]
        return None
    except (RequestException, json.JSONDecodeError):
        return None


def get_collection_guid(collection_name: str) -> str:
    """
    Convert collection name to GBIF collection key (GUID).
    Returns the first match or None if no matches found.
    """
    if not collection_name or not collection_name.strip():
        return None

    search_url = (
        f"https://api.gbif.org/v1/grscicoll/collection/search?q={collection_name}"
    )
    try:
        response = make_request_with_retry(search_url, max_retries=2, base_delay=0.5)
        data = response.json()

        if data.get("results") and len(data["results"]) > 0:
            return data["results"][0]["key"]
        return None
    except (RequestException, json.JSONDecodeError):
        return None


# Generate URL
def generate_gbif_search_url(
    fields: dict,
    institution_key: str,
    institution_code: str,
    collection_code: str,
    offset: int = 0,
) -> str:
    processed_fields = fields.copy()

    # Convert institution name to GUID if present
    if "institution" in processed_fields:
        institution_guid = get_institution_guid(processed_fields["institution"])
        if institution_guid:
            processed_fields["institutionKey"] = institution_guid
        # Remove the original text field
        del processed_fields["institution"]

    # Convert collection name to GUID if present
    if "collection" in processed_fields:
        collection_guid = get_collection_guid(processed_fields["collection"])
        if collection_guid:
            processed_fields["collectionKey"] = collection_guid
        # Remove the original text field
        del processed_fields["collection"]

    params = []
    if institution_key:
        params.append(f"institutionKey={institution_key}")
    if institution_code and institution_code.strip():
        params.append(f"institutionCode={institution_code}")
    if collection_code and collection_code.strip():
        params.append(f"collectionCode={collection_code}")
    base_url = f"{GBIF_API_BASE_URL}?{urlencode(processed_fields)}&limit=300&offset={offset}&basisOfRecord=PRESERVED_SPECIMEN"
    if params:
        base_url += "&" + "&".join(params)
    return base_url


def make_request_with_retry(url, max_retries=3, base_delay=1, timeout=30):
    """
    Make HTTP request with exponential backoff retry logic.

    Args:
        url: URL to request
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        timeout: Request timeout in seconds

    Returns:
        requests.Response object

    Raises:
        RequestException: If all retry attempts fail
    """
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except (ConnectionError, Timeout) as e:
            if attempt == max_retries:
                raise RequestException(
                    f"Failed after {max_retries + 1} attempts: {str(e)}"
                )

            # Calculate delay with exponential backoff + jitter
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            time.sleep(delay)
        except requests.HTTPError as e:
            # Don't retry on client errors (4xx), but retry on server errors (5xx)
            if 400 <= e.response.status_code < 500:
                raise e
            elif attempt == max_retries:
                raise RequestException(
                    f"Failed after {max_retries + 1} attempts: {str(e)}"
                )

            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            time.sleep(delay)
        except RequestException as e:
            if attempt == max_retries:
                raise e

            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            time.sleep(delay)


# Generate table
def generate_table(search_url: str, condensed_table: bool):
    """
    Takes the json response of a GBIF api call and creates a streamlit table.
    """
    try:
        response = make_request_with_retry(search_url, max_retries=3, base_delay=1)
        if len(response.json()["results"]) == 0:
            st.error("No values were found for your query. Please try again.")
            return None
    except RequestException as e:
        st.error(f"Failed to fetch data from GBIF API: {str(e)}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        st.error(f"Received invalid response {str(e)} from GBIF API. Please try again.")
        return None

    df = pd.DataFrame(response.json()["results"])
    df["key"] = "https://gbif.org/occurrence/" + df["key"].astype("str")
    df = df.rename({"key": "link"}, axis=1)

    # Handle images
    if "media" in df.columns:

        def extract_media_info(media_list):
            if not media_list or not isinstance(media_list, list):
                return "", ""
            identifiers = []
            for media_item in media_list:
                if isinstance(media_item, dict) and "identifier" in media_item:
                    identifiers.append(media_item["identifier"])

            if not identifiers:
                return "", ""

            # Return first URL and count
            first_url = identifiers[0]
            count = len(identifiers)
            return (
                first_url,
                f"View image{' (' + str(count) + ')' if count > 1 else ''}",
            )

        media_info = df["media"].apply(extract_media_info)
        df["media_url"] = [info[0] for info in media_info]
    col_order = [
        "link",
        "catalogNumber",
        "scientificName",
        "eventDate",
        "recordedBy",
        "locality",
        "media_url",
    ]
    existing_cols = [col for col in col_order if col in df.columns]
    if condensed_table:
        return df[existing_cols]
    return df


@st.fragment
def display_results(condensed_table: bool):
    """Fragment that handles data display and pagination independently"""
    if not (
        st.session_state.search_params and st.session_state.search_params["fields"]
    ):
        return

    try:
        offset = st.session_state.current_page * 300
        search_url = generate_gbif_search_url(
            st.session_state.search_params["fields"],
            institution_key=st.session_state.search_params["institution_key"],
            institution_code=st.session_state.search_params["institution_code"],
            collection_code=st.session_state.search_params["collection_code"],
            offset=offset,
        )

        # Use st.status for page loading
        page_num = st.session_state.current_page + 1
        with st.status(
            f"Generating results table for page {page_num}", expanded=True
        ) as status:
            df = generate_table(search_url, condensed_table)
            if df is not None:
                status.update(label="Data loaded", state="complete")
            else:
                status.update(label="No results found", state="error")

        if df is not None:
            if df["recordedBy"].str.contains("|").any():
                df["recordedBy"] = df["recordedBy"].str.split("|")
                st.dataframe(
                    df,
                    column_config={
                        "link": st.column_config.LinkColumn(
                            "link", display_text="View record"
                        ),
                        "recordedBy": st.column_config.ListColumn(),
                        "media_url": st.column_config.LinkColumn(
                            "image",
                            display_text="View image",
                        ),
                    },
                    hide_index=True,
                )
            else:
                st.dataframe(
                    df,
                    column_config={
                        "link": st.column_config.LinkColumn(
                            "link", display_text="View record"
                        ),
                        "media_url": st.column_config.LinkColumn(
                            "image",
                            display_text="View image",
                        ),
                    },
                    hide_index=True,
                )

            # Pagination controls
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("← Previous", disabled=st.session_state.current_page == 0):
                    st.session_state.current_page -= 1
                    st.rerun(scope="fragment")  # Only rerun this fragment

            with col2:
                st.write(f"Page {st.session_state.current_page + 1}")

            with col3:
                if st.button("Next →", disabled=len(df) < 300):
                    st.session_state.current_page += 1
                    st.rerun(scope="fragment")  # Only rerun this fragment

            st.markdown(f"[**Open raw GBIF search results**]({search_url})")

    except Exception:
        st.error("Sorry something went wrong.")


def main():
    st.markdown(
        """
    <style>
        section[data-testid="stSidebar"] {
            width: 500px !important; # Set the width to your desired value
        }
    </style>
    """,
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.logo(
            image="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0Ij48ZyBmaWxsPSIjMzE4NjJjIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGNsaXAtcnVsZT0iZXZlbm9kZCI+PHBhdGggZD0iTTIyLjU4NiAxMC4xNzNhMi4yNSAyLjI1IDAgMCAxLTIuMTc3LS41ODJsLS41NDEtLjU0MWE0Ljc1IDQuNzUgMCAwIDEtNS4xOS03LjM3MWE3LjcgNy43IDAgMCAwLTEuNjA0LS4zNzZBMTEgMTEgMCAwIDAgMTIgMS4yNUM2LjA2MyAxLjI1IDEuMjUgNi4wNjMgMS4yNSAxMmMwIDEuODU2LjQ3MSAzLjYwNSAxLjMgNS4xM2wtLjc4NyA0LjIzM2EuNzUuNzUgMCAwIDAgLjg3NC44NzRsNC4yMzMtLjc4OEExMC43IDEwLjcgMCAwIDAgMTIgMjIuNzVjNS45MzcgMCAxMC43NS00LjgxMyAxMC43NS0xMC43NXEwLS41NDMtLjA1My0xLjA3NHMtLjA0NS0uMzI1LS4xMTEtLjc1M00xOS45NyA1Ljk3YS43NS43NSAwIDAgMSAxLjA2IDBsMS41IDEuNWEuNzUuNzUgMCAwIDEtMS4wNiAxLjA2bC0xLjUtMS41YS43NS43NSAwIDAgMSAwLTEuMDYiLz48cGF0aCBkPSJNMTguNSAyLjc1YTEuNzUgMS43NSAwIDEgMCAwIDMuNWExLjc1IDEuNzUgMCAwIDAgMC0zLjVNMTUuMjUgNC41YTMuMjUgMy4yNSAwIDEgMSA2LjUgMGEzLjI1IDMuMjUgMCAwIDEtNi41IDAiLz48L2c+PC9zdmc+",
            size="large",
        )
        st.markdown("# GBIF Natural Language Search")
        with st.expander(label="Overview", expanded=True):
            st.markdown("""
                    This tool helps researchers search GBIF for preserved specimens through natural language queries. Enter your query in natural language in the search box, and press search. Results will be processed and a table will display with the results. You can download the results as a csv file by hovering over the table and pressing the download icon.

                    Some things that you can search for:
                    - Taxonomic searches, scientific name or common name are supported
                    - Records from a particular institution or collection
                    - Records from a particular place (continent, country, or location description)
                    - Records collected at a particular time. Ranges are supported.
                    - Records collected by a particular person.
                        """)
        with st.expander(label="Privacy and disclaimers", expanded=False):
            st.markdown("""
                    Queries are parsed by ChatGPT o4-mini. Any text entered in the search box will be sent to OpenAI and be visible to the developers. You may review the privacy policy of OpenAI [here](https://openai.com/policies/row-privacy-policy/). This project is not endorsed or affiliated with GBIF. This tool comes with no uptime warranties or guarantees.
                        """)
        with st.expander(label="Source code", expanded=False):
            st.markdown("""

                    The source code for this application is available on [GitHub](https://github.com/mark-pitblado/gbif-chat-search) under an MIT license. The logo is from [iconoir](https://iconoir.com/) and is also under an MIT license.
                        """)

    st.markdown("## Search")
    user_query = st.text_input(
        "Enter your specimen search query",
        placeholder="e.g. Blue Jays from Toronto",
    )
    with st.expander("Manual configuration options"):
        # Attempt to get the institution key from the environment if set
        institution_key = os.getenv("INSTITUTION_KEY")
        # If not configured, give the user the opportunity to narrow down their searches.
        if not institution_key:
            st.markdown(
                "If you would like to filter your results to a particular institution or collection, enter those values below. The search will attempt to parse these values from your query, however can be unreliable."
            )
            col1, col2 = st.columns(2)
            with col1:
                institution_code = st.text_input(
                    "Institution Code",
                    placeholder="e.g. BBM",
                )
            with col2:
                collection_code = st.text_input(
                    "Collection Code",
                    placeholder="e.g. CTC",
                )

    if "current_page" not in st.session_state:
        st.session_state.current_page = 0
    if "search_params" not in st.session_state:
        st.session_state.search_params = None

    condensed_table = st.toggle(
        label="Condensed results table",
        value=True,
    )
    search_clicked = st.button("SEARCH")

    if search_clicked and user_query:
        # Reset to first page on new search
        st.session_state.current_page = 0
        st.session_state.search_params = {
            "fields": None,
            "institution_key": institution_key,
            "institution_code": institution_code
            if "institution_code" in locals()
            else None,
            "collection_code": collection_code
            if "collection_code" in locals()
            else None,
        }

        with st.spinner("Processing query..."):
            try:
                fields = extract_query_fields(user_query)
                st.session_state.search_params["fields"] = fields
                st.subheader("Interpreted parameters")
                st.table(fields)
            except Exception:
                st.error("Sorry something went wrong. Please try again.")

    display_results(condensed_table=condensed_table)


if __name__ == "__main__":
    main()
