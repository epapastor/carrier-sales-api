

The structure of the following project: 

carrier-sales-api/
├── app/
│   ├── main.py          → FastAPI app entry point
│   ├── config.py        → API key auth + negotiation settings
│   ├── database.py      → SQLite setup
│   ├── models.py        → All request/response schemas
│   └── routers/
│       ├── carrier.py   → POST /verify-carrier (FMCSA + mock)
│       ├── loads.py     → POST /search-loads
│       ├── negotiation.py → POST /evaluate-offer (3-round logic)
│       ├── calls.py     → POST /log-call + GET /calls
│       └── metrics.py   → GET /metrics + GET /metrics/daily
├── data/loads.json      → 6 mock loads
├── seed_demo_data.py    → Seeds 40 demo calls for dashboard
├── Dockerfile           → Container setup
├── docker-compose.yml   → Local deployment
├── requirements.txt
└── README.md            → Full documentation
