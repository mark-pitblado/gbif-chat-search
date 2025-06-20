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
    page_title="GBIF Plain Language Search",
    page_icon="🌿",
    layout="wide",
)


def extract_query_fields(user_input):
    prompt = f"""

    You are a chatbot helping users convert natural langauge prompts into Global Biodiversity Information FacilityAPI fields.

    Extract the taxonomy (scientific_name), location (locality), continent (continent), country (country), state/province (stateProvince), collector (recordedBy), collection date (eventDate), and mediaType from this user query: '{user_input}'.

    Return the result as a JSON dictionary using only valid gbif api parameters as keys if mentioned. For example, these are some examples of valid keys:
        'scientificName', 'locality', 'continent', 'country', 'stateProvince', 'recordedBy', 'eventDate', "mediaType"

    Additional instructions:
        - Use 'location' only for geographic localities, lakes, cities, landmarks, etc.
        - Only use recordedBy for human names.
        - Output should be valid JSON only.
        - If there is a range, separate the values by a ,
        - If there is a country specified, use the two letter code for that country in capital letters as the value.
        - If the user enters the common name for a scientific name, such as "Sparrow", use the scientific name that best fits that common name.
    """
    response = client.chat.completions.create(
        model="o4-mini-2025-04-16", messages=[{"role": "user", "content": prompt}]
    )
    extracted = response.choices[0].message.content
    return json.loads(extracted)


# Generate URL
def generate_gbif_search_url(fields, institution_key):
    if institution_key and institution_key.strip():
        return f"{GBIF_API_BASE_URL}?{urlencode(fields)}&institutionKey={institution_key}&limit=300"
    return f"{GBIF_API_BASE_URL}?{urlencode(fields)}&limit=300"


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
                Enter queries like 'Birds collected in British Columbia in 2000'. This tool uses ChatGPT o4-mini. Any text entered in the text box below will be sent to OpenAI. You may review their privacy policy [here](https://openai.com/policies/row-privacy-policy/). This project is not endorsed or affiliated with GBIF.

                """)

    user_query = st.text_input(
        "Enter your specimen search query",
        placeholder="e.g. Blue Jays from Toronto",
    )
    # Attempt to get the institution key from the environment if set
    institution_key = os.getenv("INSTITUTION_KEY")
    # If not configured, give the user the opportunity to enter it.
    if not institution_key:
        institution_key = st.text_input(
            "To limit searches to a particular institution, input the institutions identifier key here",
            placeholder="36046980-307d-43e0-93ce-d4e599162e93",
        )
    search_clicked = st.button("SEARCH")

    if search_clicked and user_query:
        with st.spinner("Processing query..."):
            try:
                fields = extract_query_fields(user_query)
                st.subheader("Interpreted parameters")
                st.table(fields)

                search_url = generate_gbif_search_url(
                    fields, institution_key=institution_key
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
