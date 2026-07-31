# Phase 1: Database Schema & Setup
**Date:** 2026-07-31
**Status:** Completed
**Module:** Database
**Next Phase:** [[Phase 2 - FastAPI Core & Admin Setup]]

## 🎯 Objectives
1. Design a highly normalized and scalable database schema for the PriceGuard system.
2. Ensure the schema supports location-based queries (for the Admin Heatmap) and historical price tracking.
3. Categorize commodities effectively for the mobile app interface (Vegetables, Fruits, Dairy, Poultry & Meat).
4. Deploy the schema to a cloud-based PostgreSQL environment for seamless collaboration.

## 🛠️ Tech Stack & Infrastructure
- **Database Engine:** PostgreSQL
- **Hosting:** Neon (Serverless, Cloud-based)
  - *Storage:* 500 MB (Sufficient, as we store image URLs, not raw image files).
  - *Compute:* Shared vCPU, wakes up on API requests.
- **ORM:** SQLAlchemy (Python)

## 🗄️ Core Tables & Relationships
- **Users:** Manages authentication and roles (`citizen`, `admin`).
- **Categories & Commodities:** One-to-Many relationship. Contains seed data for daily-use items.
- **Markets/Zones:** Stores `latitude` and `longitude` which is critical for mapping green/red zones on the Streamlit dashboard.
- **Official_Rates:** Connects `commodity_id` and `market_id`.
- **Complaints:** Connects users to the issues they report. Stores `receipt_image_url` and `ai_extracted_price`.

## 📝 Key Architectural Decisions
- **Rate History Logic:** We avoided creating a redundant `rate_history` table. Instead, history is maintained natively within the `Official_Rates` table using the `effective_date` column.
- **Image Storage Strategy:** To preserve the 500 MB Neon database limit, actual receipt images will be uploaded to a cloud storage bucket (e.g., Cloudinary/AWS), and only their string URLs (`receipt_image_url`) are saved in the database.
- **Indexing:** Applied database indexes on `effective_date` and `market_id` to ensure fast data retrieval when generating heatmaps.

---

# Phase 2: FastAPI Core & Admin Setup
**Date:** 2026-07-31
**Status:** In Progress
**Module:** Backend
**Previous Phase:** [[Phase 1 - Database Schema]]

## 🎯 Objectives
1. Set up the core FastAPI application structure.
2. Implement secure User Authentication (Signup/Login) using JWT.
3. Establish Role-Based Access Control (RBAC) to differentiate between `citizen` and `admin`.
4. Create an endpoint for Admins to upload daily commodity rates via CSV/Excel.

## 🛠️ Tech Stack & Libraries Used
- **FastAPI:** Core web framework.
- **SQLAlchemy:** ORM for database operations.
- **Neon (PostgreSQL):** Cloud database for storing records.
- **Passlib & Bcrypt:** For secure password hashing.
- **Python-JOSE:** For encoding and decoding JWT tokens.
- **Pandas:** To parse and process the admin's CSV/Excel rate files.

## 📝 Key Workflows Implemented
- **Database Dependency (`get_db`):** Ensures every API request safely opens and closes a connection to the Neon database.
- **JWT Authentication (`get_current_user`):** Protects specific routes so only logged-in users can access them.
- **Admin Verification (`get_admin_user`):** A secondary check ensuring that only users with the `admin` role can upload rate lists.
- **Rate History Logic:** Instead of updating old rows or keeping a separate history table, the CSV upload endpoint inserts new rows into the `Official_Rates` table using the current date (`effective_date`). This naturally builds a historical timeline.

## ⚠️ Important Considerations
- Passwords are never stored in plain text.
- The CSV upload feature assumes columns like `Item Name`, `Unit`, and `Price`. The backend must map these `Item Names` exactly to the `commodities` table IDs.

---

