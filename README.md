Enphase savings calculator
 
Tool to help determine savings from adding or modifying components to a home monitored by Enphase.

For example:
- How much money would be saved by adding a battery to a solar system?
- How much money would be saved by adding solar panels?

Prior logged data from Enphase is used to simulate savings.

To run:
```
./venv/Scripts/activate
python app.py
```

### Setup Requirements
- Python 3.8 or higher
- Pip (Python package manager)
- Virtual environment (`venv`)

#### Installation Steps:
1. Clone the repository
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   ./venv/Scripts/activate  # On Windows
   source venv/bin/activate # On macOS/Linux
   ```
3. Install required Python packages:
   ```
   pip install -r requirements.txt
   ```

#### Environment Variables:
Set the following environment variables:
- `ENPHASE_API_KEY`: Your Enphase API key
- `ENPHASE_CLIENT_ID`: Your Enphase Client ID
- `ENPHASE_SAVINGS_CALCULATOR_SECRET`: A secret key for Flask session management. Set this to anything you like.


### Usage
1. Open a web browser to `http://localhost:5000/`
2. Login or create an account
3. Connect to your Enphase account
4. Choose your system
5. Download telemetry data for the desired weeks in your dashboard.
6. Navigate to the simulation page
7. Populate simulation parameters and simulate!
   ![image](https://github.com/user-attachments/assets/0f14c1bf-ac49-4b3c-8b53-b8d7f60e195d)

9. Review simulation results and download CSV

![image](https://github.com/user-attachments/assets/75923292-7eb3-4bae-927a-0d1a5f200d34)

![image](https://github.com/user-attachments/assets/c56352e8-3100-40b9-a863-51bffe7f5017)

---
![image](https://github.com/user-attachments/assets/d7d64766-4a5e-4190-9dfb-7c9d1e90845c)
