from PIL import Image
import numpy as np

def detect_manipulation(image_path):
    try:
        img = Image.open(image_path)
        img_array = np.array(img)
        
        noise_level = np.std(img_array) / 255.0
        
        manipulation_score = min(noise_level * 2, 1.0)
        
        return float(manipulation_score)
    except Exception as e:
        return 0.0
