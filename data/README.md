# Data directories

The ETL process uses a three-stage local layout:

- `raw/`: locally supplied Baseball Savant exports and the pitch-keyed video-link table
- `processed/`: generated, analysis-ready pitch datasets
- `sample/`: optional small, intentionally curated data safe for public demonstration

Raw and processed files are excluded from Git. The application stores official video URLs, not video files.
