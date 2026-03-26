CREATE DATABASE IF NOT EXISTS misinformation_db;
USE misinformation_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    username VARCHAR(80) NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inputs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    content TEXT,
    file_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    input_id INT NOT NULL,
    prediction VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    manipulation_score FLOAT,
    report_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (input_id) REFERENCES inputs(id) ON DELETE CASCADE
);

INSERT INTO users (email, username, password, role) VALUES 
('admin@example.com', 'admin', 'scrypt:32768:8:1$ixVnBrgfp6cH1HsZ$ce2e0e9a2c8e3f4e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c2e3e6e5c6b0c', 'admin');
