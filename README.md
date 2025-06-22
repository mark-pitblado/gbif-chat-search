# GBIF Chat Search

A Streamlit web application that enables researchers to search the Global Biodiversity Information Facility (GBIF) database using natural language queries. The app converts these searches into GBIF API parameters using OpenAI's language model and displays preserved specimen records in an interactive table.

## Features

- **Natural Language Search**: Enter queries like "Blue Jays from Toronto" or "specimens collected by Darwin in 1835"
- **Intelligent Query Parsing**: Uses OpenAI's o4-mini model to extract taxonomic names, locations, dates, collectors, and institutions from natural language.
- **GBIF Integration**: Automatically converts institution and collection names to proper GBIF identifiers.
- **Interactive Results**: View results in a paginated table with direct links to GBIF records and specimen images.
- **Robust Error Handling**: Includes retry logic and graceful error handling for API requests.

## Setup

### Prerequisites

- Python 3.11 and [uv](https://docs.astral.sh/uv/getting-started/installation/) (if running through streamlit)
- Docker engine (if running through docker)
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/mark-pitblado/gbif-chat-search.git
cd gbif-chat-search
```

2. Install dependencies:
```bash
uv sync
```

3. Create a `.env` file in the project root:
```bash
GBIF_CHAT_OPENAI_API_KEY=your_openai_api_key_here
# Optional: Set default institution key to filter results
INSTITUTION_KEY=your_institution_key_here
```

4. Run the application:
```bash
uv run streamlit run app.py
```

## Docker Deployment

### Using Docker

```bash
# Build the image
docker build -t gbif-chat-search .

# Run the container
docker run -p 8501:8501 --env-file .env gbif-chat-search
```

### Using Docker Compose

1. Create a `compose.yml` file:
```yaml
services:
  gbif-chat-search:
    build: .
    ports:
      - "8501:8501"
    environment:
      - GBIF_CHAT_OPENAI_API_KEY=${GBIF_CHAT_OPENAI_API_KEY}
      - INSTITUTION_KEY=${INSTITUTION_KEY}
    env_file:
      - .env
    restart: unless-stopped
```

2. Deploy with Docker Compose:
```bash
docker-compose up -d
```

### Production Deployment

For production deployments, consider:

- Using a reverse proxy (nginx, caddy) for SSL termination
- Setting up proper logging and monitoring
- Using Docker secrets for sensitive environment variables
- Implementing health checks and restart policies

## Usage

1. **Enter Search Query**: Type your search in natural language (e.g., "Sparrows collected in California after 2010")

2. **Review Interpreted Parameters**: The app will show how it interpreted your query into GBIF search parameters

3. **Browse Results**: View results in the interactive table with links to full GBIF records and specimen images

4. **Navigate Pages**: Use pagination controls to browse through large result sets (300 records per page)

5. **Export Data**: Use Streamlit's built-in export functionality to download results as CSV

## Query Examples

- `"Blue Jays from Toronto"`
- `"specimens collected by Darwin"`
- `"birds from Museum of Natural History"`
- `"plants collected in Brazil between 1990-2000"`
- `"mammals with images from California"`

## Privacy & Disclaimers

- All search queries are sent to OpenAI for processing.
- Review [OpenAI's privacy policy](https://openai.com/policies/row-privacy-policy/) before use.
- This tool is not affiliated with or endorsed by GBIF.
- No uptime warranties or guarantees provided.
