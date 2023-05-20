from __future__ import print_function

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
#-------------------------------------------------
import speech_recognition as sr
import time
import os
from gtts import gTTS
import random
import playsound
import datetime 
import pytz

#----------------------------------------------

from vosk import Model, KaldiRecognizer
import pyaudio
model = Model(model_name = "vosk-model-small-en-us-0.15")
recognizer = KaldiRecognizer(model, 16000)
#-------------------------------------------

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']


#-----------------------------------------------------------------------

# Checking the authentication for google calendar
def authenticate_google_calendar():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('credentials/calendar/token.json'):
        creds = Credentials.from_authorized_user_file('credentials/calendar/token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials/calendar/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('credentials/calendar/token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
    except HttpError as error:
        print('An error occurred: %s' % error)
        
    return service
#-------------------------------------------------------------------------------------------------

# Define constants for months, days of the week, and day extensions
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
DAY_EXTENTIONS = ['st', 'nd', 'rd', 'th']

def get_date(text):
    # Convert input text to lowercase for case-insensitive matching
    text = text.lower()
    # Get today's date
    today = datetime.date.today()

    # Check if the input text contains the word "today"
    if text.count("today") > 0:
        return today
    
    # Check if the input text contains the phrase "day after tomorrow"
    if text.count("day after tomorrow") > 0:
        day_after_tomorrow = today + datetime.timedelta(2)
        return day_after_tomorrow
    
    # Check if the input text contains the word "tomorrow"
    if text.count("tomorrow") > 0:
        tomorrow = today + datetime.timedelta(1)
        return tomorrow
    
    # Initialize variables for day, day of the week, month, and year
    day = -1
    day_of_week = -1
    month = -1
    year = today.year

    # Loop through each word in the input text and check if it matches with a month, day of the week, or day
    for word in text.split():
        if word in MONTHS:
            # If the word matches with a month, set the month variable accordingly
            month = MONTHS.index(word) + 1
        elif word in DAYS:
            # If the word matches with a day of the week, set the day_of_week variable accordingly
            day_of_week = DAYS.index(word)
        elif word.isdigit():
            # If the word is a number, set the day variable accordingly
            day = int(word)
        else:
            for ext in DAY_EXTENTIONS:
                found = word.find(ext)
                if found > 0:
                    try:
                        # If the word contains a day extension, extract the number before the extension and set the day variable accordingly
                        day = int(word[:found])
                    except:
                        pass

    # Check if the month mentioned is before the current month and set the year to the next year if so
    if month < today.month and month != -1:
        year = year+1

    # If we didn't find a month but we have a day, set the month based on whether the day is before or after today's date
    if month == -1 and day != -1:
        if day < today.day:
            month = today.month + 1
        else:
            month = today.month

    # If we only found a day of the week, calculate the number of days until that day and return the date
    if month == -1 and day == -1 and day_of_week != -1:
        current_day_of_week = today.weekday()
        dif = day_of_week - current_day_of_week
        
        if dif < 0:
            dif += 7
            if text.count("next") >= 1:
                dif += 7

        return today + datetime.timedelta(dif)

    # If we found a day, return the date object with the month, day, and year values

#------------------------------------------------------------------------------------------

def get_events(day, service):
    # Call the Google Calendar API to retrieve events for the specified day
    date = datetime.datetime.combine(day, datetime.datetime.min.time())
    end_date = datetime.datetime.combine(day, datetime.datetime.max.time())

    # Convert the date and end_date to UTC timezone
    utc = pytz.UTC
    date = date.astimezone(utc)
    end_date = end_date.astimezone(utc)

    # Use the 'list' method of the Google Calendar API to retrieve events from the primary calendar
    events_result = service.events().list(calendarId='primary', timeMin=date.isoformat(), timeMax=end_date.isoformat(),
                                          singleEvents=True, orderBy='startTime').execute()

    # Get the list of events for the specified day
    events = events_result.get('items', [])

    # If there are no events for the specified day, return a message indicating this
    if not events:
        assistant_speak('No upcoming events found.')
        return
    
    # If there are one or more events, return a message indicating how many events there are
    else:
        if len(events) == 1:
            assistant_speak("You have " + str({len(events)}) + " event on this day.")
        else:
            assistant_speak("You have " + str({len(events)}) + " events on this day.")

    # Iterate through each event and get its start time and summary (name)
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))

        # Get the start time of the event in a human-readable format
        start_time = str(start.split("T")[1].split("-")[0])

        # Convert the start time to 12-hour time format with AM/PM designation
        hr_start_time = int(start_time[0:2]) * 1
        min_start_time = int(start_time[3:5]) * 1
        
        # Add leading zero to minutes if less than 10
        if min_start_time > 0 and min_start_time < 10:
            min_start_time = str("0" + str(min_start_time))
        elif min_start_time == 0:
            min_start_time = ""
        else:
            min_start_time = min_start_time
        
        # Create human-readable time format with AM/PM designation
        if hr_start_time < 12 and min_start_time != "":
            start_time = str(hr_start_time) + " " + str(min_start_time) + " " + "AM"
        elif hr_start_time < 12:
            start_time = str(hr_start_time) + " AM"

        if hr_start_time > 12 and min_start_time != "":
            start_time = str(hr_start_time - 12) + " " + str(min_start_time) + " " + "PM"
        elif hr_start_time > 12:
            start_time = str(hr_start_time - 12) + " PM"

        # Speak the summary (name) of the event and its start time
        assistant_speak(event["summary"] + " at " + start_time)
        
        
#--------------------------------------------------------------------
# Create a recognizer object for speech recognition
r = sr.Recognizer()

# Initialize a variable to hold the recognized speech
voice_data=""

# Function to record audio input from the user using a microphone
def record_audio():
#     # Use the default system microphone as the audio source
#     with sr.Microphone() as source:
#         # Adjust the energy threshold dynamically based on the ambient noise level
#         r.adjust_for_ambient_noise(source, duration=0.1)  
#         r.dynamic_energy_threshold = True
#         # Record audio from the microphone
#         audio = r.listen(source)
#         # Convert the recorded audio to text using Google's speech recognition service
#         voice_data = ''
#         try:
#             voice_data = r.recognize_google(audio)
#         except sr.UnknownValueError:
#             # If the speech cannot be recognized, do nothing and return an empty string
#             pass
#         except sr.RequestError:
#             # If there is an error with the speech recognition service, notify the user and return an empty string
#             assistant_speak("Sorry, I did not get that")
#         return voice_data
    
    
    mic = pyaudio.PyAudio()
    stream = mic.open(format = pyaudio.paInt16, channels = 1, rate =16000, input = True, frames_per_buffer=8192)
    #stream = mic.open(format = pyaudio.paInt16, channels = 1, rate = 16000, input = True, frames_per_buffer=8192)
    stream.start_stream()
    
#------------------------------------------------------


# Function to convert text to speech using Google's Text-to-Speech API
def assistant_speak(text):
    
    # Create a Text-to-Speech (TTS) object using the given text and language
    tts = gTTS(text=text, lang='en')
    # Generate a random integer to use as a unique identifier for the audio file
    r = random.randint(1, 10000000)
    # Save the TTS output as an MP3 audio file with the unique identifier in the filename
    audio_file  = 'audio-' +str(r) + '.mp3'
    tts.save(audio_file)
    # Play the audio file using the system default audio player
    playsound.playsound(audio_file)
    # Delete the audio file from the local directory to save disk space
    os.remove(audio_file)

#-----------------------------------------------------------------------------------------

import pulsectl

pulse = pulsectl.Pulse('set-volume-example')
default_sink = pulse.sink_list()[0]
pulse.volume_set_all_chans(default_sink, 1)
#-------------------------------------------------------------------------

# set the username
username = 'john'

# authenticate with Google Calendar API
wake = "hello " + username
service = authenticate_google_calendar()

mic = pyaudio.PyAudio()
stream = mic.open(format = pyaudio.paInt16, channels = 1, rate =16000, input = True, frames_per_buffer=8192)
text = "A"
frame =[]

while True:
    data = stream.read(4096)
    if recognizer.AcceptWaveform(data):
        text = recognizer.Result()
        print("Raw " + text)
        text = text[14:-3]
        
        if text.count(wake) > 0:
            print("this is what recorded " + str(text))
            
            assistant_speak('How can I help you?')
            
            frame.append(text)
            
            
    if len(frame)>0:
        
        if frame[0] == "hello " + username:
            CALENDAR_STRS = ["what do i have", "do i have plans", "am i busy", "tell me my appointment", "any plans"]
            for phrase in CALENDAR_STRS:
                if phrase in text.lower():
                    date = get_date(text)
                    if date:
                        get_events(date, service)
                        frame = []
                    else:
                        assistant_speak("Please try again")
                        frame = []           
