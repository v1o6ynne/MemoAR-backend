# MemoAR Backend 🚀

This is the FastAPI backend for the MemoAR project, hosted on Railway. It processes 2D images into 3D models using the Tripo AI engine and stores the results in Supabase for iOS AR integration.

🔗 Quick Links for testing API with Swagger UI: https://memoar-backend-production.up.railway.app/docs

## Database config

- `DATABASE_URL`: backend Postgres used by `memories`, `user_app_usage`, `api_process_records`, and `notification_records`

## Notification records

`/writeData/notification-record`, `/readData/notification-records/{user_id}`, and `/readData/notification-record/{record_id}` read and write `notification_records` through the same `DATABASE_URL` connection as the other backend records.

## Memory deletion

`POST /writeData/delete-memory` accepts `user_id` and `memory_id`. It removes only the matching row from `memories`; stored images, models, and historical notification records are retained. Deleting an already absent row succeeds with `deleted: false`, allowing safe retries.

Run the isolated deletion tests with `python -m unittest discover -s tests -v`.
