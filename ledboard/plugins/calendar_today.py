import os
from datetime import datetime
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
    max_lines = 6

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
            "lines": [],
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

    def _fetch_events_for_calendar(self, calendar_info, time_min, max_results=20):
        events = self.service.events().list(
            calendarId=calendar_info["id"],
            timeMin=time_min,
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        ).execute()

        items = events.get("items", [])
        for item in items:
            item["_calendar_name"] = calendar_info["name"]
            item["_calendar_id"] = calendar_info["id"]
        return items

    def _format_time_short(self, dt):
        hour = dt.hour
        minute = dt.minute
        suffix = "A" if hour < 12 else "P"
        hour12 = hour % 12
        if hour12 == 0:
            hour12 = 12

        if minute == 0:
            return f"{hour12}{suffix}"
        return f"{hour12}:{minute:02d}{suffix}"

    def _truncate_to_width(self, draw, text, font, max_width):
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return text

        ellipsis = "…"
        lo = 0
        hi = len(text)
        best = ellipsis

        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = text[:mid].rstrip() + ellipsis
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if width <= max_width:
                best = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return best

    def refresh(self):
        tz = ZoneInfo(self.timezone)
        now = datetime.now(tz)

        future_events = []
        for cal in self.calendar_ids:
            try:
                items = self._fetch_events_for_calendar(
                    cal,
                    now.isoformat(),
                    max_results=15,
                )
                future_events.extend(items)
            except Exception as e:
                print(f"[calendar] failed reading {cal['name']}: {e}")

        sortable = []
        for event in future_events:
            start_dt, is_all_day = self._parse_event_start(event, tz)
            if start_dt is not None:
                sortable.append((start_dt, 0 if is_all_day else 1, event, is_all_day))

        sortable.sort(key=lambda x: (x[0], x[1]))

        dedup = []
        seen = set()
        for start_dt, _, event, is_all_day in sortable:
            key = (
                event.get("id"),
                event.get("summary", ""),
                event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
            )
            if key in seen:
                continue
            seen.add(key)

            dedup.append(
                {
                    "title": event.get("summary", "(No title)"),
                    "date": start_dt.strftime("%m/%d"),
                    "time": "" if is_all_day else self._format_time_short(start_dt),
                }
            )
            if len(dedup) >= self.max_lines:
                break

        self.state = {
            "lines": dedup,
        }
        super().refresh()

    def render(self, width, height):
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        try:
            font_row = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
            font_meta = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 11)
        except Exception:
            font_row = ImageFont.load_default()
            font_meta = ImageFont.load_default()

        draw.rectangle((0, 0, width - 1, height - 1), outline=(40, 100, 40))

        lines = self.state.get("lines", [])
        if not lines:
            draw.text((6, 24), "No upcoming events", font=font_row, fill=(190, 190, 190))
            return image

        row_y = 2
        row_step = 10
        time_right_x = width - 6
        date_w = 28
        gap = 4

        for item in lines[: self.max_lines]:
            date_text = item.get("date", "")
            time_text = item.get("time", "")
            title = item.get("title", "")

            time_w = 0
            if time_text:
                bbox = draw.textbbox((0, 0), time_text, font=font_meta)
                time_w = bbox[2] - bbox[0]
                draw.text(
                    (time_right_x - time_w, row_y),
                    time_text,
                    font=font_meta,
                    fill=(255, 210, 80),
                )

            date_x = time_right_x - time_w - gap - date_w
            draw.text(
                (date_x, row_y),
                date_text,
                font=font_meta,
                fill=(150, 150, 150),
            )

            title_max_right = date_x - gap
            title_max_width = max(10, title_max_right - 6)
            title = self._truncate_to_width(draw, title, font_row, title_max_width)

            draw.text((6, row_y), title, font=font_row, fill=(235, 235, 235))
            row_y += row_step

        return image

