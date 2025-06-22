import json
import openai
import requests
import streamlit as st
import pandas as pd
import os

from urllib.parse import urlencode
from dotenv import load_dotenv

# Set up API client

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("GBIF_CHAT_OPENAI_API_KEY"))
GBIF_API_BASE_URL = "https://api.gbif.org/v1/occurrence/search"

# Setup settings for app
st.set_page_config(
    page_title="GBIF Natural Language Search",
    page_icon="🌿",
    layout="wide",
)


def extract_query_fields(user_input):
    prompt = f"""

    You are a chatbot helping users convert natural langauge prompts into Global Biodiversity Information FacilityAPI fields.

    Extract the taxonomy (scientific_name), location (locality), collection, institution, continent (continent), country (country), state/province (stateProvince), collector (recordedBy), collection date (eventDate), and mediaType from this user query: '{user_input}'.

    Return the result as a JSON dictionary using only valid gbif api parameters as keys if mentioned. For example, these are some examples of valid keys:
        'scientificName', 'locality', 'continent', 'country', 'stateProvince', 'recordedBy', 'eventDate', "mediaType"

    Additional instructions:
        - Output should be valid JSON only.
        - Use 'location' only for geographic localities, lakes, cities, landmarks, etc. Do not put the collection or institution value in this field.
        - Only use recordedBy for human names.
        - The name of the collection, if present, should be assigned to the "collection" key in the JSON.
        - The name of the institution, if present, should be assigned to the "institution" key in the JSON.
        - If there is a range, separate the values by a ,
        - If there is a country specified, use the two letter code for that country in capital letters as the value.
        - If the user enters the common name for a scientific name, such as "Sparrow", use the scientific name that best fits that common name.
    """
    response = client.chat.completions.create(
        model="o4-mini-2025-04-16", messages=[{"role": "user", "content": prompt}]
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
        response = requests.get(search_url)
        response.raise_for_status()
        data = response.json()

        if data.get("results") and len(data["results"]) > 0:
            return data["results"][0]["key"]
        return None
    except requests.RequestException:
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
        response = requests.get(search_url)
        response.raise_for_status()
        data = response.json()

        if data.get("results") and len(data["results"]) > 0:
            return data["results"][0]["key"]
        return None
    except requests.RequestException:
        return None


# Generate URL
def generate_gbif_search_url(
    fields: dict, institution_key: str, institution_code: str, collection_code: str
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
    base_url = f"{GBIF_API_BASE_URL}?{urlencode(processed_fields)}&limit=300&basisOfRecord=PRESERVED_SPECIMEN"
    if params:
        base_url += "&" + "&".join(params)
    return base_url


# Generate table
def generate_table(search_url: str):
    """
    Takes the json response of a GBIF api call and creates a streamlit table.
    """
    response = requests.get(search_url)
    if len(response.json()["results"]) == 0:
        st.error("No values were found for your query. Please try again.")
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
    return df[existing_cols]


def main():
    st.markdown("""

                # GBIF Natural Language Search
                This tool helps researchers search GBIF through natural language queries.
                This tool uses ChatGPT o4-mini. Any text entered in the text box below will be sent to OpenAI. You may review their privacy policy [here](https://openai.com/policies/row-privacy-policy/). This project is not endorsed or affiliated with GBIF.

                """)

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
                    placeholder="e.g. ROM",
                )
            with col2:
                collection_code = st.text_input(
                    "Collection Code",
                    placeholder="e.g. BIRDS",
                )

    search_clicked = st.button("SEARCH")

    if search_clicked and user_query:
        with st.spinner("Processing query..."):
            try:
                fields = extract_query_fields(user_query)
                st.subheader("Interpreted parameters")
                st.table(fields)

                search_url = generate_gbif_search_url(
                    fields,
                    institution_key=institution_key,
                    institution_code=institution_code,
                    collection_code=collection_code,
                )
                df = generate_table(search_url)
                if df is not None:
                    st.dataframe(
                        generate_table(search_url),
                        column_config={
                            "link": st.column_config.LinkColumn(
                                "link", display_text="View record"
                            ),
                            "media_url": st.column_config.LinkColumn(
                                "image",
                                display_text=df["media_display"]
                                if "media_display" in df.columns
                                else "View image",
                            ),
                        },
                        hide_index=True,
                    )
                st.markdown(f" [**Open raw GBIF search results**]({search_url})")
            except Exception:
                st.error("Sorry something went wrong. Please try again.")


if __name__ == "__main__":
    main()
