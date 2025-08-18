# Frappe CRM Assistant - AI Call Note Creator

The Frappe CRM Assistant is an AI-powered tool designed to streamline CRM workflows by automatically transcribing call recordings and generating detailed notes. This tool integrates with the Frappe CRM, leveraging the Deepgram API for accurate speech-to-text conversion.

## Purpose

This tool solves the common problem of manually logging notes after customer calls. By automating the transcription process, it saves time for sales and support teams, improves the accuracy of call records, and ensures that valuable information from conversations is never lost.

## Target Users

- **Sales Representatives:** To automatically log call details and focus on selling.
- **Customer Support Agents:** To maintain accurate records of support calls for future reference.
- **CRM Administrators:** To ensure data consistency and completeness within the CRM.

## Key Features

- **Automatic Transcription:** Transcribes audio recordings from CRM Call Logs into text.
- **Note Creation:** Automatically creates a new "FCRM Note" for each transcribed call.
- **CRM Integration:** Links the generated notes to the relevant CRM documents (Lead, Deal, or Customer).
- **Batch Processing:** Can process multiple call logs at once or fetch the last 'N' calls for transcription.
- **Secure:** Uses the Frappe framework's permission model to ensure only authorized users can create notes.

## Installation Steps

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
# Navigate to your Frappe Bench directory
cd $PATH_TO_YOUR_BENCH

# Get the app from its GitHub repository
bench get-app $URL_OF_THIS_REPO --branch main

# Install the app on your site
bench --site your-site-name.localhost install-app frappe_crm_assistant
```

## Configuration

To use the transcription feature, you need a Deepgram API key.

1.  **Get a Deepgram API Key:** Sign up at [Deepgram](https://deepgram.com/) to get your free API key.
2.  **Set the API Key:** Add the key to your site's configuration file (`sites/your-site-name.localhost/site_config.json`):
    ```json
    {
        "deepgram_api_key": "YOUR_DEEPGRAM_API_KEY"
    }
    ```

## Usage Examples

The tool can be triggered via the Frappe Assistant interface. Here are some example queries:

- **Transcribe a single call:**
  `"Create a note from call log CRM-CL-00001"`

- **Transcribe multiple calls:**
  `"Create notes from call logs CRM-CL-00001, CRM-CL-00002, and CRM-CL-00003"`

- **Transcribe the last 5 completed calls:**
  `"Generate notes for the last 5 calls"`

## Screenshots

*(Please add screenshots or a GIF of the tool in action. For example, show the Frappe Assistant chat window with a sample query, and the resulting "FCRM Note" that is created.)*

![Screenshot of Frappe Assistant](placeholder.png "Frappe Assistant Query")
![Screenshot of Generated Note](placeholder.png "Generated Note")

## Technical Documentation

### Architecture Overview

The tool operates within the Frappe Assistant ecosystem. The workflow is as follows:

1.  A user invokes the `generate_notes_from_calls` tool via the Frappe Assistant.
2.  The tool fetches the specified `CRM Call Log` document(s).
3.  It retrieves the `recording_url` from the call log.
4.  The audio file is downloaded and streamed to the Deepgram API (`https://api.deepgram.com/v1/listen`).
5.  Deepgram processes the audio and returns a JSON response containing the transcription.
6.  The tool creates a new `FCRM Note` document with the transcription as its content.
7.  The new note is linked back to the original `CRM Call Log` and any associated Lead, Deal, or Customer.

### Dependencies

- **Frappe Framework:** Version 15 or higher.
- **Frappe Assistant Core:** The underlying framework for creating AI tools.
- **Python `requests` library:** For making HTTP requests to the Deepgram API.

### Known Issues

- The accuracy of the transcription depends on the audio quality and the Deepgram API's performance.
- Currently supports only MP3 audio format as per the default configuration.

---

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/frappe_crm_assistant
pre-commit install
```

### License

MIT