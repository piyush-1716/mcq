import json
import urllib.request
import urllib.error

# Replace with your key or read from environment variable
API_KEY = "apikey_2125333ab2981a414b869eb691ee222a745e_c825200c54b8d353d86b889a9b1a5480a279263a4b83e512140adc50e1fee131"

def test_models():
    print("Testing TypeSafe API Key (Models Endpoint)...")
    url = "https://api.typesafe.ai/v1/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {API_KEY}"})
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"[+] Status Code: {resp.status} OK")
            print(f"[+] Available Models: {json.dumps(data, indent=2)}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[-] HTTP Error {e.code}: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"[-] Connection Error: {e}")
        return False

def test_inference():
    print("\nTesting TypeSafe Inference (SystemOne)...")
    url = "https://api.typesafe.ai/v1/systemone"
    payload = {
        "model": "jev-latest",
        "state": "The server CPU usage is at 99% and response times are spiking.",
        "questions": {
            "is_critical": {
                "type": "noul",
                "instructions": "Is this a critical system issue?"
            }
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"[+] Status Code: {resp.status} OK")
            print(f"[+] Prediction Result:\n{json.dumps(data, indent=2)}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[-] HTTP Error {e.code}: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"[-] Connection Error: {e}")
        return False

if __name__ == "__main__":
    if test_models():
        test_inference()
