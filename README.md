# MemoAR Backend 🚀

This is the FastAPI backend for the MemoAR project, hosted on Railway. It processes 2D images into 3D models using the Tripo AI engine and stores the results in Supabase for iOS AR integration.

🔗 Quick Links for testing API with Swagger UI: https://memoar-backend-production.up.railway.app/docs

## Database config

- `DATABASE_URL`: primary backend Postgres used by `memories`, `user_app_usage`, `capture_surveys`, and `api_process_records`
- `SUPABASE_DATABASE_URL` or `SUPABASE_DB_URL`: Supabase Postgres used specifically by `notification_records`

## Notification records

`/writeData/notification-record`, `/readData/notification-records/{user_id}`, and `/readData/notification-record/{record_id}` now read and write `notification_records` through the dedicated Supabase Postgres connection above.
