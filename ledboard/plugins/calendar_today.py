import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from plugin_base import BasePlugin

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class CalendarTodayPlugin(BasePlugin):
    name = "calendar"
    refresh_seconds = 300
    display_seconds = 12

    def __init__(self, app_context):
        super().__init__(app_context)
        self.timezone = os.environ.get("TIMEZONE", "America/Los_Angeles")
        self.service = self._build_service()

        raw_ids = os.environ.get(
            "GOOGLE_CALENDAR_IDS",
            "primary,Holidays in United States,Joel Berman (TripIt)",
        )
        self.calendar_refs = [x.strip() for x in raw_ids.split(",") if x.strip()]
        self.calendar_ids = self._resolve_calendar_ids(self.calendar_refs)

        self.state = {
            "headline": "CALENDAR",
            "title": "Loading...",
            "time": "",
            "location": "",
            "subtitle": "",
        }

    def _build_service(self):
        creds = None

        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open("token.json", "w") as token:
                token.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    def _resolve_calendar_ids(self, refs):
        resolved = []

        calendar_list = self.service.calendarList().list().execute().get("items", [])
        by_summary = {}

        for cal in calendar_list:
            summary = cal.get("summary", "").strip()
            cal_id = cal.get("id", "").strip()

            if summary:
                by_summary[summary.lower()] = {
                    "id": cal_id,
                    "name": summary,
                }

            if cal_id:
                by_summary[cal_id.lower()] = {
                    "id": cal_id,
                    "name": summary or cal_id,
                }

        for ref in refs:
            key = ref.lower()
            if key in by_summary:
                resolved.append(by_summary[key])
            else:
                resolved.append({"id": ref, "name": ref})

        seen = set()
        deduped = []
        for item in resolved:
            if item["id"] not in seen:
                seen.add(item["id"])
                deduped.append(item)

        return deduped

    def _parse_event_start(self, event, tz):
        start = event.get("start", {})

        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt, False

        if "date" in start:
            dt = datetime.fromisoformat(start["date"]).replace(tzinfo=tz)
            return dt, True

        return None, False

    def _parse_event_end(self, event, tz, is_all_day):
        end = event.get("end", {})

        if "dateTime" in end:
            dt = datetime.fromisoformat(end["dateTime"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt

        if "date" in end:
            dt = datetime.fromisoformat(end["date"]).replace(tzinfo=tz)
            return dt

        start_dt, _ = self._parse_event_start(event, tz)
        if start_dt is None:
            return None

        if is_all_day:
            return start_dt + timedelta(days=1)

        return start_dt + timedelta(hours=1)

    def _fetch_events_for_calendar(self, calendar_info, time_min, time_max, max_results=20):
        events = self.service.events().list(
            calendarId=calendar_info["id"],
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        ).execute()

        items = events.get("items", [])
        for item in items:
            item["_calendar_name"] = calendar_info["name"]
            item["_calendar_id"] = calendar_info["id"]
        return items

    def refresh(self):
        tz = ZoneInfo(self.timezone)
        now = datetime.now(tz)

        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today = start_of_today + timedelta(days=1)

        all_today_events = []

        for cal in self.calendar_ids:
            try:
                items = self._fetch_events_for_calendar(
                    cal,
                    start_of_today.isoformat(),
                    end_of_today.isoformat(),
                    max_results=20,
                )
                all_today_events.extend(items)
            except Exception as e:
                print(f"[calendar] failed reading {cal['name']}: {e}")

        sortable_today = []
        for event in all_today_events:
            start_dt, is_all_day = self._parse_event_start(event, tz)
            if start_dt is not None:
                sortable_today.append((start_dt, 0 if is_all_day else 1, event))

        sortable_today.sort(key=lambda x: (x[0], x[1]))
        today_events = [x[2] for x in sortable_today]

        chosen = None
        headline = "TODAY"

        for event in today_events:
            start_dt, is_all_day = self._parse_event_start(event, tz)
            end_dt = self._parse_event_end(event, tz, is_all_day)

            if start_dt is None or end_dt is None:
                continue

            if is_all_day:
                if start_dt.date() <= now.date() < end_dt.date():
                    chosen = event
                    headline = "NOW"
                    break
            else:
                if start_dt <= now < end_dt:
                    chosen = event
                    headline = "NOW"
                    break

        if chosen is None:
            for event in today_events:
                start_dt, _ = self._parse_event_start(event, tz)
                if start_dt is not None and start_dt >= now:
                    chosen = event
                    headline = "TODAY"
                    break

        if chosen is None:
            future_candidates = []

            for cal in self.calendar_ids:
                try:
                    future = self.service.events().list(
                        calendarId=cal["id"],
                        timeMin=now.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                        maxResults=5,
                    ).execute()

                    items = future.get("items", [])
                    for item in items:
                        item["_calendar_name"] = cal["name"]
                        item["_calendar_id"] = cal["id"]
                        start_dt, is_all_day = self._parse_event_start(item, tz)
                        if start_dt is not None:
                            future_candidates.append((start_dt, 0 if is_all_day else 1, item))
                except Exception as e:
                    print(f"[calendar] failed future lookup for {cal['name']}: {e}")

            future_candidates.sort(key=lambda x: (x[0], x[1]))

            if future_candidates:
                chosen = future_candidates[0][2]
                headline = "NEXT"
            else:
                self.state = {
                    "headline": "CALENDAR",
                    "title": "No upcoming events",
                    "time": "",
                    "location": "",
                    "subtitle": "",
                }
                super().refresh()
                return

        summary = chosen.get("summary", "(No title)")
        location = chosen.get("location", "")

        start_dt, is_all_day = self._parse_event_start(chosen, tz)
        end_dt = self._parse_event_end(chosen, tz, is_all_day)

        if start_dt is None:
            time_text = ""
            subtitle = ""
        elif is_all_day:
            time_text = "All day"
            subtitle = start_dt.strftime("%a %b ").strip() + str(start_dt.day)
        else:
            time_text = (
                f"{start_dt.strftime('%I:%M %p').lstrip('0')} - "
                f"{end_dt.strftime('%I:%M %p').lstrip('0')}"
            )
            subtitle = start_dt.strftime("%a %b ").strip() + str(start_dt.day)

        self.state = {
            "headline": headline,
            "title": summary,
            "time": time_text,
            "location": location,
            "subtitle": subtitle,
        }
        super().refresh()

    def render(self, width, height):
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        try:
            font_head = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 12
            )
            font_title = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 15
            )
            font_med = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 11
            )
            font_small = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 10
            )
        except Exception:
            font_head = ImageFont.load_default()
            font_title = ImageFont.load_default()
            font_med = ImageFont.load_default()
            font_small = ImageFont.load_default()

        draw.rectangle((0, 0, width - 1, height - 1), outline=(40, 100, 40))

        draw.text((4, 3), self.state["headline"], font=font_head, fill=(120, 255, 140))

        subtitle = self.state.get("subtitle", "")
        if subtitle:
            subtitle_bbox = draw.textbbox((0, 0), subtitle, font=font_small)
            subtitle_w = subtitle_bbox[2] - subtitle_bbox[0]
            draw.text(
                (width - subtitle_w - 6, 4),
                subtitle,
                font=font_small,
                fill=(120, 120, 120),
            )

        title = self.state.get("title", "")
        if len(title) > 34:
            title = title[:33] + "…"
        draw.text((6, 19), title, font=font_title, fill=(235, 235, 235))

        time_text = self.state.get("time", "")
        draw.text((6, 39), time_text, font=font_med, fill=(255, 210, 80))

        location = self.state.get("location", "")
        if location:
            if len(location) > 22:
                location = location[:21] + "…"
            draw.text((92, 39), location, font=font_small, fill=(170, 170, 170))

        return image

