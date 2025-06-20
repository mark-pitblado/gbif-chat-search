# GBIF Chat Search

This streamlit app allows the user to enter a natural langauge query and have results returned as a table which can then be viewed in the web interface, or downloaded as a csv file.

## Demo

There is a demo of this application at <https://chat.dwca.net>. There is no uptime guarantee or availability guarantees, the applicaiton may be taken down once API tokens are exhausted. The demo application is set to search all of GBIF and uses Open AI's o4-mini model.

## Installation

If you wish to host this application, you should clone this repository, and set your own API key as an environment variable. Optionally, you may set an institution key to limit search results to records from your instituion.

```dotenv
OPENAI_API_KEY=your_key_here
INSTITUION_KEY=your_institution_key here #optional
```
