import boto3
import os
from dotenv import load_dotenv

# 1. Load the keys from your .env file
load_dotenv()

# 2. Get variables from environment
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
bucket_name = os.getenv("AWS_S3_BUCKET_NAME")

print(f"Checking connection for bucket: {bucket_name}...")

# 3. Initialize the S3 Client
try:
    s3 = boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key
    )

    # 4. Try to list objects in the bucket
    response = s3.list_buckets()
    print("✅ SUCCESS: Connected to AWS!")
    print("Your available buckets:")
    for bucket in response['Buckets']:
        print(f"  - {bucket['Name']}")

except Exception as e:
    print("❌ FAILED: Could not connect.")
    print(f"Error: {e}")