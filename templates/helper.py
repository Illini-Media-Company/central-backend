from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


@app.route("/")
def home():
    # Render your Jinja2 HTML template
    return render_template("di_contract_automization_admin.html")  # Use your file name


@app.route("/send_agreement", methods=["POST"])
def send_agreement():
    try:
        # Get JSON data from the frontend
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON received"}), 400

        # Extract fields from JSON
        emails = data.get("emails", [])
        manager = data.get("manager")
        chief = data.get("chief")

        # Validate required fields
        if not emails or not manager or not chief:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required fields (emails, manager, or chief).",
                    }
                ),
                400,
            )

        # ✅ You can now process this data:
        # e.g. store in a database, trigger email automation, etc.
        print("📨 Agreement submission received:")
        print(f"Manager: {manager}")
        print(f"Chief: {chief}")
        print(f"Emails: {emails}")

        # Example: create response payload
        response = {
            "status": "success",
            "message": f"Agreements sent to {len(emails)} employees.",
            "emails": emails,
        }

        return jsonify(response), 200

    except Exception as e:
        print("Error in /send_agreement:", e)
        return jsonify({"status": "error", "message": "Server error occurred"}), 500


if __name__ == "__main__":
    app.run(debug=True)
