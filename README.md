# Distributed File Storage System 🚀
[![Storage System CI](https://github.com/Yugal810/Distributed-file-storage/actions/workflows/main.yml/badge.svg)](https://github.com/Yugal810/Distributed-file-storage/actions/workflows/main.yml)

A FastAPI-based backend that shards files across multiple storage nodes for optimized management.

## 🛠 Features
* **Sharding:** Automatically splits file chunks into node1, node2, and node3.
* **CI/CD:** Automated testing via GitHub Actions.
* **Docker Ready:** Includes a Dockerfile for containerized deployment.
* **Search:** Metadata-based search functionality.

## 🚀 How to Run
1. Navigate to the backend: `cd backend`
2. Install requirements: `pip install -r requirements.txt`
3. Run the app: `uvicorn app.main:app --reload`