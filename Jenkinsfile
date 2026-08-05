pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Verify Tools') {
            steps {
                sh 'whoami'
                sh 'git --version'
                sh 'docker --version'
                sh 'kubectl version --client'
                sh 'helm version'
                sh 'aws --version'
                sh 'python3 --version'
            }
        }
    }
}
