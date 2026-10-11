import json
import os
import matplotlib.pyplot as plt

original_json = '[{"Date":"2025-09-01","Website_Visits":542},{"Date":"2025-09-02","Website_Visits":489},{"Date":"2025-09-03","Website_Visits":563},{"Date":"2025-09-04","Website_Visits":512},{"Date":"2025-09-05","Website_Visits":0},{"Date":"2025-09-06","Website_Visits":598},{"Date":"2025-09-07","Website_Visits":621},{"Date":"2025-09-08","Website_Visits":505},{"Date":"2025-09-09","Website_Visits":0},{"Date":"2025-09-10","Website_Visits":534},{"Date":"2025-09-11","Website_Visits":511},{"Date":"2025-09-12","Website_Visits":490},{"Date":"2025-09-13","Website_Visits":523},{"Date":"2025-09-14","Website_Visits":514},{"Date":"2025-09-15","Website_Visits":2500},{"Date":"2025-09-16","Website_Visits":527},{"Date":"2025-09-17","Website_Visits":499},{"Date":"2025-09-18","Website_Visits":5545},{"Date":"2025-09-19","Website_Visits":488},{"Date":"2025-09-20","Website_Visits":531}]'
cleaned_json = '[{"Date": "2025-09-01", "Website_Visits": 542}, {"Date": "2025-09-02", "Website_Visits": 489}, {"Date": "2025-09-03", "Website_Visits": 563}, {"Date": "2025-09-04", "Website_Visits": 512}, {"Date": "2025-09-06", "Website_Visits": 598}, {"Date": "2025-09-07", "Website_Visits": 621}, {"Date": "2025-09-08", "Website_Visits": 505}, {"Date": "2025-09-10", "Website_Visits": 534}, {"Date": "2025-09-11", "Website_Visits": 511}, {"Date": "2025-09-12", "Website_Visits": 490}, {"Date": "2025-09-13", "Website_Visits": 523}, {"Date": "2025-09-14", "Website_Visits": 514}, {"Date": "2025-09-16", "Website_Visits": 527}, {"Date": "2025-09-17", "Website_Visits": 499}, {"Date": "2025-09-19", "Website_Visits": 488}, {"Date": "2025-09-20", "Website_Visits": 531}]'

original_data = json.loads(original_json)
cleaned_data = json.loads(cleaned_json)

original_dates = [row['Date'] for row in original_data]
original_visits = [row['Website_Visits'] for row in original_data]

cleaned_dates = [row['Date'] for row in cleaned_data]
cleaned_visits = [row['Website_Visits'] for row in cleaned_data]

plt.figure(figsize=(12,6))
plt.plot(original_dates, original_visits, color='blue', label='Original Data')
plt.plot(cleaned_dates, cleaned_visits, color='green', label='Cleaned Data')
plt.xlabel('Date')
plt.ylabel('Website Visits')
plt.title('Website Visits: Original vs Cleaned Data')
plt.xticks(rotation=45)
plt.legend()
plt.tight_layout()

os.makedirs('artifacts', exist_ok=True)
plt.savefig('artifacts/data_visualization.png')
plt.close()