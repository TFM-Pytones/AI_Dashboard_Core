import pandas as pd
from utils.azure_storage import get_container_client
import io

container_client = get_container_client()
blob_client = container_client.get_blob_client("booking/booking_reviews_2026-08-02_132123.parquet")
data = blob_client.download_blob().readall()
df = pd.read_parquet(io.BytesIO(data))

print(repr(df["review_date"].iloc[0]))
print(repr(df["reviewer_country"].iloc[0]))