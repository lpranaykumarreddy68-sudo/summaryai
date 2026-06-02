import sys
import os

# Ensure the root directory is in python path for serverless imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mangum import Mangum
from main import app

handler = Mangum(app)
