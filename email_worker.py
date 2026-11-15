import pandas as pd
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DB_FILE = "market_snapshot.db"

def send_email():
    # 1. Load the database
    if not os.path.exists(DB_FILE):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM daily_snapshot", conn)
    conn.close()

    # 2. Sort exactly like your app.py (Score Desc, P/B Asc)
    df['pb_float'] = pd.to_numeric(df['pb'], errors='coerce').fillna(999.0)
    df = df.sort_values(by=['score', 'pb_float'], ascending=[False, True]).drop(columns=['pb_float'])
    
    # 3. Get Top 3
    top_3 = df.head(3)

    # 4. Format Email
    sender_email = os.environ.get("EMAIL_SENDER")
    sender_password = os.environ.get("EMAIL_PASSWORD")
    receiver_email = os.environ.get("EMAIL_RECEIVER")

    if not all([sender_email, sender_password, receiver_email]):
        print("Missing email credentials in environment variables.")
        return

    subject = "🚀 11 AM Alert: Top 3 Opportunity Scanner Picks"
    body = "<h2>🏛️ Top 3 Opportunities (All Sectors)</h2><ul>"
    
    for _, row in top_3.iterrows():
        target = row['price'] * 1.10
        body += f"<li><strong>{row['ticker']}</strong> ({row['sector']})<br>"
        body += f"Current Price: ₹{row['price']:.2f} | Target (+10%): ₹{target:.2f}<br>"
        body += f"Score: {row['score']}/18 | P/B: {row['pb']} | BV: ₹{row.get('book_value', 0.0):.2f}</li><br>"
    
    body += "</ul><p>Log in to your Streamlit App to view the full matrix.</p>"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    # 5. Send Email
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    send_email()
