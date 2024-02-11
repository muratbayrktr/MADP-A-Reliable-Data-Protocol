#!/bin/bash

# List all server script files
server_scripts=($(ls ./code/testcases/*_server.sh))

# Loop through each server script
for server_script in "${server_scripts[@]}"; do
    for i in {1..5}; do
        # Extract the basename without the path and the extension
        base_name=$(basename "$server_script" "_server.sh")

        case_name="${base_name%%_*}"


        # Determine the corresponding client script
        client_script="./code/testcases/${base_name}_client.sh"

        # Check if the client script exists
        if [[ ! -f "$client_script" ]]; then
            echo "Client script for $base_name does not exist."
            continue
        fi

        # Extract the percent or identifier (assuming the format is like corrupt_10_server.sh)
        percent=$(echo "$base_name" | grep -o -E '[0-9]+')

        echo "Run[$i][$case_name][$percent%]:"
        echo "${base_name}_client.sh"
        echo "${base_name}_server.sh"

        # Start the receiver (client) Docker container and run the script
        docker run --rm --privileged --cap-add=NET_ADMIN --name ceng435client -d -v ./code:/app:rw ceng435:latest ../app/testcases_tcp/${base_name}_server.sh

        # Allow some time for the receiver container to initialize
        sleep 1

        # Start the sender (server) Docker container and run the script
        docker run --rm --privileged --cap-add=NET_ADMIN --name ceng435server -v ./code:/app:rw ceng435:latest ../app/testcases_tcp/${base_name}_client.sh

        # Wait for the sender to finish
        sleep 1

        # Stop the containers
        # if containers are not stopped then stop them
        if [[ $(docker ps -a | grep ceng435client) ]]; then
            docker stop ceng435client
        fi
        if [[ $(docker ps -a | grep ceng435server) ]]; then
            docker stop ceng435server
        fi
        # docker stop ceng435client 
        # docker stop ceng435server

        # Additional wait for safe cleanup if needed
        sleep 1
    done

done
