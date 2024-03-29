"""
Support for Dublin Bus, Irish Rail and Transport for Ireland Journey Planner
(https://journeyplanner.transportforireland.ie/) RTPI information sources.

For more info on the TFI API see:
https://www.transportforireland.ie/transitData/PT_Data.html
https://code.google.com/archive/p/openefa/wikis
https://github.com/opendata-stuttgart/metaEFA
"""
import logging
from datetime import timedelta, datetime
from abc import ABCMeta
from pyirishrail.pyirishrail import IrishRailRTPI

from xml.dom import minidom
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

# REQUIREMENTS = ['pyirishrail==0.0.2']

_LOGGER = logging.getLogger(__name__)
DUBLIN_BUS_RESOURCE = "https://data.smartdublin.ie/cgi-bin/rtpi/realtimebusinformation"
TFI_EFA_RESOURCE = "https://journeyplanner.transportforireland.ie/nta/XSLT_DM_REQUEST"

RTPI_TIMEOUT = 4

ATTR_STOP_ID = "stop_id"
ATTR_ROUTE = "route"
ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"
ATTR_DIRECTION = "direction"
ATTR_COUNTDOWN = "countdown"
ATTR_DUE_AT = "due_at"
ATTR_SCHEDULED_AT = "scheduled_at"
ATTR_STOPS_AT = "stops_at"
ATTR_IS_REALTIME = "is_realtime"
ATTR_DEPARTURES = "departures"
ATTR_DEPARTURES_TEXT = "departures_text"
ATTR_DEPARTURES_HTML = "departures_html"
ATTR_DEPARTURES_MD = "departures_md"
ATTR_DEPARTURES_JSON = "departures_json"
ATTR_SECOND_DEPARTURE = "second_departure"
ATTR_SOURCE = "source"

ATTR_SOURCE_WARNING = "source_warning"

CONF_ATTRIBUTION = "Data provided by transportforireland.ie per conditions of reuse at https://data.gov.ie/licence"
CONF_STOP_ID = "stop_id"
CONF_ROUTE = "route"
CONF_ROUTE_LIST = "route_list"
CONF_DIRECTION = "direction"
CONF_DIRECTION_INVERSE = "direction_inverse"
CONF_RTPI_SOURCES = "rtpi_sources"
CONF_SHOW_OPTIONS = "show_options"
CONF_REALTIME_ONLY = "realtime_only"
CONF_SKIP_NO_RESULTS = "skip_no_results"  ## skip source if no results
CONF_LIMIT_TIME_HORIZON = "limit_time_horizon"
CONF_LIMIT_DEPARTURES = "limit_departures"
CONF_SSL_VERIFY = "ssl_verify"
CONF_REFRESH_INTERVAL = "refresh_interval"
CONF_NO_DATA_REFRESH_INTERVAL = "no_data_refresh_interval"
CONF_FAST_REFRESH_THRESHOLD = "fast_refresh_threshold"

CONF_SHOW_ROUTE = "show_route"
CONF_SHOW_REALTIME = "show_realtime"

DEFAULT_NAME = "Transport for Ireland Departures"
DEFAULT_REFRESH_INTERVAL = 1
DEFAULT_NO_DATA_REFRESH_INTERVAL = 60
DEFAULT_LIMIT_TIME_HORIZON = 90

ICON = "mdi:bus"

SCAN_INTERVAL = timedelta(seconds=30)
TIME_STR_FORMAT = "%H:%M"

SHOW_OPTIONS = [
    ATTR_DEPARTURES_TEXT,
    ATTR_DEPARTURES_HTML,
    ATTR_DEPARTURES_MD,
    ATTR_DEPARTURES_JSON,
    ATTR_SCHEDULED_AT,
    ATTR_DUE_AT,
    ATTR_SECOND_DEPARTURE,
    CONF_SHOW_ROUTE,
    CONF_SHOW_REALTIME,
]

# RTPI data sources
RTPI_SOURCE_TFI_EFA_XML = "tfi_efa_xml"
RTPI_SOURCE_TFI_EFA = "tfi_efa"
RTPI_SOURCE_DUBLIN_BUS = "dublin_bus"
RTPI_SOURCE_IRISH_RAIL = "irish_rail"

# Sources are evaluated in specified order of precedence: data from later
# sources overrides data from earlier sources
RTPI_SOURCES = [
    RTPI_SOURCE_TFI_EFA_XML,
    RTPI_SOURCE_TFI_EFA,
    RTPI_SOURCE_DUBLIN_BUS,
    RTPI_SOURCE_IRISH_RAIL,
]

# CONF_RTPI_SCHEMA = vol.Schema({cv.slug: cv.string})

CONF_RTPI_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_STOP_ID, default=""): cv.string,
        vol.Optional(CONF_ROUTE, default=""): cv.string,
        vol.Optional(CONF_ROUTE_LIST, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DIRECTION, default=None): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_DIRECTION_INVERSE, default=False): cv.boolean,
        vol.Optional(CONF_REALTIME_ONLY, default=False): cv.boolean,
        vol.Optional(CONF_SKIP_NO_RESULTS, default=False): cv.boolean,
        vol.Optional(CONF_SSL_VERIFY, default=True): cv.boolean,
    }
)

CONF_RTPI_SCHEMA = vol.Schema(
    {
        vol.Optional(RTPI_SOURCE_TFI_EFA_XML): CONF_RTPI_SOURCE_SCHEMA,
        vol.Optional(RTPI_SOURCE_TFI_EFA): CONF_RTPI_SOURCE_SCHEMA,
        vol.Optional(RTPI_SOURCE_DUBLIN_BUS): CONF_RTPI_SOURCE_SCHEMA,
        vol.Optional(RTPI_SOURCE_IRISH_RAIL): CONF_RTPI_SOURCE_SCHEMA,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(
            CONF_RTPI_SOURCES, default={RTPI_SOURCE_TFI_EFA: {CONF_STOP_ID: ""}}
        ): CONF_RTPI_SCHEMA,
        vol.Optional(CONF_SHOW_OPTIONS, default=list(SHOW_OPTIONS)): vol.All(
            cv.ensure_list, [vol.In(SHOW_OPTIONS)]
        ),
        vol.Optional(
            CONF_REFRESH_INTERVAL, default=DEFAULT_REFRESH_INTERVAL
        ): cv.positive_int,
        vol.Optional(
            CONF_NO_DATA_REFRESH_INTERVAL, default=DEFAULT_NO_DATA_REFRESH_INTERVAL
        ): cv.positive_int,
        vol.Optional(
            CONF_LIMIT_TIME_HORIZON, default=DEFAULT_LIMIT_TIME_HORIZON
        ): cv.positive_int,
        vol.Optional(CONF_LIMIT_DEPARTURES, default=0): cv.positive_int,
        vol.Optional(CONF_FAST_REFRESH_THRESHOLD, default=0): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dublin public transport sensor."""
    name = config.get(CONF_NAME)
    stop_id = config.get(CONF_STOP_ID)
    rtpi_sources = config.get(CONF_RTPI_SOURCES)
    show_options = config.get(CONF_SHOW_OPTIONS)
    limit_time_horizon = config.get(CONF_LIMIT_TIME_HORIZON)
    limit_departures = config.get(CONF_LIMIT_DEPARTURES)
    ssl_verify = config.get(CONF_SSL_VERIFY)
    refresh_interval = config.get(CONF_REFRESH_INTERVAL)
    no_data_refresh_interval = config.get(CONF_NO_DATA_REFRESH_INTERVAL)
    fast_refresh_threshold = config.get(CONF_FAST_REFRESH_THRESHOLD)

    for source in rtpi_sources:
        source_data = rtpi_sources[source]
        _LOGGER.debug(
            f"{stop_id}: Source: {source} "
            f"[stop_id: {source_data[CONF_STOP_ID]}, "
            f"route: {source_data[CONF_ROUTE]}, "
            f"route_list: {source_data[CONF_ROUTE_LIST]}, "
            f"direction: {source_data[CONF_DIRECTION]} "
            f"(inverse: {source_data[CONF_DIRECTION_INVERSE]}), "
            f"realtime_only: {source_data[CONF_REALTIME_ONLY]}, "
            f"ssl_verify: {source_data[CONF_SSL_VERIFY]}]"
        )
        if source_data[CONF_STOP_ID] == "":
            source_data[CONF_STOP_ID] = stop_id
        if source == RTPI_SOURCE_IRISH_RAIL:
            source_data[RTPI_SOURCE_IRISH_RAIL] = IrishRailRTPI()

    data = PublicTransportData(
        stop_id,
        rtpi_sources,
        limit_time_horizon,
        limit_departures,
        refresh_interval,
        no_data_refresh_interval,
        fast_refresh_threshold,
    )

    add_entities([DublinPublicTransportSensor(name, data, stop_id, show_options)], True)


class DublinPublicTransportSensor(Entity):
    """Implementation of an Dublin public transport sensor."""

    def __init__(self, name, data, stop_id, show_options):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._stop_id = stop_id
        self._show_options = show_options
        self._departures = None
        self._current_source = None
        self._next_refresh = 0
        self._state = None

    def _render_departure_text(self, dep):
        route = dep[ATTR_ROUTE]
        destination = dep[ATTR_DESTINATION]
        is_realtime = dep[ATTR_IS_REALTIME]
        scheduled_at = dep[ATTR_SCHEDULED_AT]
        due_at = dep[ATTR_DUE_AT]
        countdown = dep[ATTR_COUNTDOWN]

        text = ""
        if CONF_SHOW_ROUTE in self._show_options:
            text += route + " "
        text += destination
        if CONF_SHOW_REALTIME in self._show_options and is_realtime:
            text += " (R)"
        if ATTR_SCHEDULED_AT in self._show_options:
            text += " " + scheduled_at.strftime("%H:%M")
        if ATTR_DUE_AT in self._show_options:
            text += " " + due_at.strftime("%H:%M")
        text += " %d min" % countdown if countdown > 0 else " Due"
        return text

    def _render_departures_text(self):
        if not self._departures:
            return None

        firstItem = True
        text = ""
        for dep in self._departures:
            if not firstItem:
                text += "\n"
            text += self._render_departure_text(dep)
            firstItem = False
        return text

    def _render_departure_html(self, dep):
        route = dep[ATTR_ROUTE]
        destination = dep[ATTR_DESTINATION]
        is_realtime = dep[ATTR_IS_REALTIME]
        scheduled_at = dep[ATTR_SCHEDULED_AT]
        due_at = dep[ATTR_DUE_AT]
        countdown = dep[ATTR_COUNTDOWN]

        html = "<tr>"
        if CONF_SHOW_ROUTE in self._show_options:
            html += '<td class="tfi_route">' + route + "</td>"
        html += '<td class="tfi_destination">' + destination + "</td>"
        if CONF_SHOW_REALTIME in self._show_options:
            html += (
                '<td class="tfi_flags">' + ("&#x23F1;" if is_realtime else "") + "</td>"
            )
        if ATTR_SCHEDULED_AT in self._show_options:
            html += (
                '<td class="tfi_scheduled_at">'
                + scheduled_at.strftime("%H:%M")
                + "</td>"
            )
        if ATTR_DUE_AT in self._show_options:
            html += '<td class="tfi_due_at">' + due_at.strftime("%H:%M") + "</td>"
        html += (
            '<td class="tfi_countdown">'
            + ("%d min" % countdown if countdown > 0 else "Due")
            + "</td></tr>\n"
        )
        return html

    def _render_departures_html(self):
        if not self._departures:
            html = '<div class="tfi_no_data">No departure data.<br>' + "Next refresh "
            if self._next_refresh < DEFAULT_LIMIT_TIME_HORIZON:
                html += f"in {self._next_refresh} mins"
            else:
                refresh_time = datetime.now() + timedelta(minutes=self._next_refresh)
                html += "at " + refresh_time.strftime("%H:%M")
            html += "</div>"
            return html

        html = '<table class="tfi_table">\n'
        for dep in self._departures:
            html += self._render_departure_html(dep)
        html += "</table>"
        return html

    def _render_departure_md(self, dep):
        route = dep[ATTR_ROUTE]
        destination = dep[ATTR_DESTINATION]
        is_realtime = dep[ATTR_IS_REALTIME]
        scheduled_at = dep[ATTR_SCHEDULED_AT]
        due_at = dep[ATTR_DUE_AT]
        countdown = dep[ATTR_COUNTDOWN]

        md = "|"
        if CONF_SHOW_ROUTE in self._show_options:
            md += " " + route + " |"
        md += " " + destination + " |"
        if CONF_SHOW_REALTIME in self._show_options:
            md += " Y |" if is_realtime else " |"
        if ATTR_SCHEDULED_AT in self._show_options:
            md += " " + scheduled_at.strftime("%H:%M") + " |"
        if ATTR_DUE_AT in self._show_options:
            md += " " + due_at.strftime("%H:%M") + " |"
        md += " %d min |" % countdown if countdown > 0 else " Due |"
        md += "\n"
        return md

    def _render_departures_md(self):
        if not self._departures:
            md = "No departure data.\nNext refresh "
            if self._next_refresh < DEFAULT_LIMIT_TIME_HORIZON:
                md += f"in {self._next_refresh} mins"
            else:
                refresh_time = datetime.now() + timedelta(minutes=self._next_refresh)
                md += "at " + refresh_time.strftime("%H:%M")
            return md

        md = "|"
        md2 = "|"
        if CONF_SHOW_ROUTE in self._show_options:
            md += " # |"
            md2 += " ---: |"
        md += " Destination |"
        md2 += " :--- |"
        if CONF_SHOW_REALTIME in self._show_options:
            md += " RT |"
            md2 += " --- |"
        if ATTR_SCHEDULED_AT in self._show_options:
            md += " Sch |"
            md2 += " ---: |"
        if ATTR_DUE_AT in self._show_options:
            md += " Due |"
            md2 += " ---: |"
        md += " In |\n"
        md2 += " ---: |\n"

        md += md2
        for dep in self._departures:
            md += self._render_departure_md(dep)
        return md

    def _render_departure_json(self, dep):
        route = dep[ATTR_ROUTE]
        destination = dep[ATTR_DESTINATION]
        is_realtime = dep[ATTR_IS_REALTIME]
        scheduled_at = dep[ATTR_SCHEDULED_AT]
        due_at = dep[ATTR_DUE_AT]
        countdown = dep[ATTR_COUNTDOWN]

        json = "{ "
        if CONF_SHOW_ROUTE in self._show_options:
            json += '"route": "' + route + '", '
        json += '"destination": "' + destination + '"'
        if CONF_SHOW_REALTIME in self._show_options:
            json += ', "is_realtime": '
            json += "true" if is_realtime else "false"
        if ATTR_SCHEDULED_AT in self._show_options:
            json += ', "scheduled_at": "' + scheduled_at.strftime("%H:%M") + '"'
        if ATTR_DUE_AT in self._show_options:
            json += ', "due_at": "' + due_at.strftime("%H:%M") + '"'
        json += ', "countdown": %d }' % countdown
        return json

    def _render_departures_json(self):
        if not self._departures:
            return "[]"

        firstItem = True
        json = "[ "
        for dep in self._departures:
            if not firstItem:
                json += ", "
            json += self._render_departure_json(dep)
            firstItem = False
        json += " ]"
        return json

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        dev_attrs = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_STOP_ID: self._stop_id,
            ATTR_DEPARTURES: self._departures,
            ATTR_SOURCE: self._current_source,
        }
        if self._departures:
            dev_attrs[ATTR_DEPARTURES] = self._departures

            dep = self._departures[0]
            dev_attrs[ATTR_DESTINATION] = dep[ATTR_DESTINATION]
            dev_attrs[ATTR_DIRECTION] = dep[ATTR_DIRECTION]
            dev_attrs[ATTR_DUE_AT] = dep[ATTR_DUE_AT]
            dev_attrs[ATTR_COUNTDOWN] = dep[ATTR_COUNTDOWN]

            if CONF_SHOW_ROUTE in self._show_options and ATTR_ROUTE in dep:
                dev_attrs[ATTR_ROUTE] = dep[ATTR_ROUTE]
            if CONF_SHOW_REALTIME in self._show_options and ATTR_IS_REALTIME in dep:
                dev_attrs[ATTR_IS_REALTIME] = dep[ATTR_IS_REALTIME]

            if ATTR_SECOND_DEPARTURE in self._show_options:
                try:
                    dep = self._departures[1]
                    dev_attrs[ATTR_SECOND_DEPARTURE] = self._render_departure_text(dep)
                except Exception:
                    pass

        if ATTR_DEPARTURES_TEXT in self._show_options:
            text = self._render_departures_text()
            if text:
                dev_attrs[ATTR_DEPARTURES_TEXT] = text
        if ATTR_DEPARTURES_HTML in self._show_options:
            html = self._render_departures_html()
            if html:
                dev_attrs[ATTR_DEPARTURES_HTML] = html
        if ATTR_DEPARTURES_MD in self._show_options:
            md = self._render_departures_md()
            if md:
                dev_attrs[ATTR_DEPARTURES_MD] = md
        if ATTR_DEPARTURES_JSON in self._show_options:
            json = self._render_departures_json()
            if json:
                dev_attrs[ATTR_DEPARTURES_JSON] = json

        return dev_attrs

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "min"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """
        Get the latest data from each data source and update the states.
        """
        if self._data.update():
            self._departures = self._data.get_departures()
            self._current_source = self._data.get_current_source()
            self._next_refresh = self._data.get_next_refresh()
            self._state = (
                self._departures[0][ATTR_COUNTDOWN] if self._departures else None
            )


class PublicTransportData:  # (metaclass=ABCMeta):
    """The Class for handling the data retrieval."""

    def __init__(
        self,
        stop_id,
        rtpi_sources,
        limit_time_horizon,
        limit_departures,
        refresh_interval,
        no_data_refresh_interval,
        fast_refresh_threshold,
    ):
        """Initialize the data object."""
        self._stop_id = stop_id
        self._rtpi_sources = rtpi_sources
        self._limit_time_horizon = limit_time_horizon
        self._limit_departures = limit_departures
        self._refresh_interval = refresh_interval
        self._no_data_refresh_interval = no_data_refresh_interval
        self._fast_refresh_threshold = fast_refresh_threshold

        self._next_refresh = 0
        self._scan_count = 0
        self._current_source = None
        self._all_departures = []
        self._departures = []
        self._next_departure = None
        self._no_data_count = 0
        self._source_warning = False

        ## Initialise sources
        for source in self._rtpi_sources:
            source_data = self._rtpi_sources[source]
            source_data[ATTR_SOURCE_WARNING] = False

    def get_departures(self):
        return self._departures

    def get_current_source(self):
        return self._current_source

    def get_next_refresh(self):
        scan_multipler = int(round(60 / SCAN_INTERVAL.total_seconds()))
        if scan_multipler < 1:
            scan_multipler = 1
        return int(round(self._next_refresh / scan_multipler))

    # @abstractmethod
    # def update_source(self):
    #     _LOGGER.error("update_source of abstract base class invoked")
    #     raise Exception
    #     return False

    def _convert_json_datetime(self, dt_json):
        """Convert JSON timestamp to datetime object."""
        return datetime(
            year=int(dt_json["year"]),
            month=int(dt_json["month"]),
            day=int(dt_json["day"]),
            hour=int(dt_json["hour"]),
            minute=int(dt_json["minute"]),
        )

    def update_source_tfi_efa(self, stop_id, ssl_verify):
        """Get the latest data from journeyplanner.transportforireland.ie"""
        params = {
            "outputFormat": "JSON",
            "coordOutputFormat": "WGS84[dd.ddddd]",
            "language": "en",
            "std3_suggestMacro": "std3_suggest",
            "std3_commonMacro": "dm",
            "mergeDep": "1",
            "mode": "direct",
            "useAllStops": "1",
            "name_dm": stop_id,
            "type_dm": "any",
        }

        response = requests.get(
            TFI_EFA_RESOURCE, params, verify=ssl_verify, timeout=RTPI_TIMEOUT
        )
        if response.status_code != 200:
            raise Exception("HTTP status: " + str(response.status_code))

        # Parse returned departure JSON data
        departures = []
        efa_data = response.json()

        for dep in efa_data["departureList"]:
            try:
                route = dep["servingLine"]["number"]
                origin = (
                    dep["servingLine"]["directionFrom"]
                    if "directionFrom" in dep["servingLine"]
                    else "unknown"
                )
                destination = dep["servingLine"]["direction"]
                now = datetime.now().replace(second=0, microsecond=0)
                direction = (
                    "Outbound"
                    if dep["servingLine"]["liErgRiProj"]["direction"] == "R"
                    else "Inbound"
                )
                scheduled_at = self._convert_json_datetime(dep["dateTime"])
                countdown = int(dep["countdown"])
                is_realtime = dep["servingLine"]["realtime"] == "1"
                if is_realtime:
                    due_at = now + timedelta(minutes=countdown)
                else:
                    due_at = scheduled_at
            except:
                _LOGGER.warning(f"Skipping malformed departure: {dep}")
            else:
                departures.append(
                    {
                        ATTR_SOURCE: "tfi_efa",
                        ATTR_ROUTE: route,
                        ATTR_DESTINATION: destination,
                        ATTR_ORIGIN: origin,
                        ATTR_DIRECTION: direction,
                        ATTR_SCHEDULED_AT: scheduled_at,
                        ATTR_DUE_AT: due_at,
                        ATTR_COUNTDOWN: countdown,
                        ATTR_IS_REALTIME: is_realtime,
                    }
                )
        departures.sort(key=lambda a: int(a[ATTR_COUNTDOWN]))
        return departures

    def _convert_xml_datetime(self, dt_xml):
        """Convert timestamp to XML datetime object."""
        date = dict(dt_xml.getElementsByTagName("itdDate")[0].attributes.items())
        time = dict(dt_xml.getElementsByTagName("itdTime")[0].attributes.items())
        return datetime(
            year=int(date["year"]),
            month=int(date["month"]),
            day=int(date["day"]),
            hour=int(time["hour"]),
            minute=int(time["minute"]),
        )

    def update_source_tfi_efa_xml(self, stop_id, ssl_verify):
        """Get the latest data from journeyplanner.transportforireland.ie (XML)"""
        params = {
            "outputFormat": "XML",
            "coordOutputFormat": "WGS84[dd.ddddd]",
            "language": "en",
            "std3_suggestMacro": "std3_suggest",
            "std3_commonMacro": "dm",
            "mergeDep": "1",
            "mode": "direct",
            "useAllStops": "1",
            "name_dm": stop_id,
            "type_dm": "any",
        }

        response = requests.get(
            TFI_EFA_RESOURCE, params, verify=ssl_verify, timeout=RTPI_TIMEOUT
        )
        if response.status_code != 200:
            raise Exception(f"HTTP status: {str(response.status_code)}")

        # Parse returned departure XML data
        departures = []
        xml_data = minidom.parseString(response.content)

        for dep in xml_data.getElementsByTagName("itdDeparture"):
            itdServingLine = dep.getElementsByTagName("itdServingLine")[0]
            motDivaParams = itdServingLine.getElementsByTagName("motDivaParams")[0]
            itdDateTime = dep.getElementsByTagName("itdDateTime")[0]
            dep_attrs = dict(dep.attributes.items())
            line_attrs = dict(itdServingLine.attributes.items())
            line_divaparams = dict(motDivaParams.attributes.items())
            route = line_attrs["number"]
            destination = line_attrs["direction"]
            origin = line_attrs["directionFrom"]
            countdown = int(dep_attrs["countdown"])
            is_realtime = line_attrs["realtime"] == "1"
            direction = line_divaparams["direction"]
            scheduled_at = self._convert_xml_datetime(itdDateTime)
            due_at = scheduled_at
            if is_realtime:
                itdRTDateTimes = dep.getElementsByTagName("itdRTDateTime")
                # itRTDateTime does not always seem to be present for
                # departures flagged realtime
                if itdRTDateTimes:
                    due_at = self._convert_xml_datetime(itdRTDateTimes[0])
                else:
                    is_realtime = False

            departures.append(
                {
                    ATTR_SOURCE: "tfi_efa_xml",
                    ATTR_ROUTE: route,
                    ATTR_DESTINATION: destination,
                    ATTR_ORIGIN: origin,
                    ATTR_DIRECTION: direction,
                    ATTR_SCHEDULED_AT: scheduled_at,
                    ATTR_DUE_AT: due_at,
                    ATTR_COUNTDOWN: countdown,
                    ATTR_IS_REALTIME: is_realtime,
                }
            )
            departures.sort(key=lambda a: int(a[ATTR_COUNTDOWN]))
        return departures

    def _convert_time(self, t):
        """Convert time string to datetime object."""
        now = datetime.now().replace(second=0, microsecond=0)
        tobj = datetime.strptime(t, "%H:%M").time()
        dt = datetime.combine(now.date(), tobj)
        if dt < now - timedelta(hours=12):  # time refers to next day
            dt = dt + timedelta(days=1)
        elif dt > now + timedelta(hours=12):  # adjust for clock skew
            dt = dt - timedelta(days=1)

        return dt

    def update_source_irish_rail(self, ir_api, stop_id, direction, ssl_verify):
        """Get the latest data from http://api.irishrail.ie."""
        # ssl_verify not supported
        # 2020-06-20 direction stopped returning Northbound and Southbound
        # for Dublin trains, so now filtering on list of directions
        # train_data = ir_api.get_station_by_name(stop_id, direction=direction)
        train_data = ir_api.get_station_by_name(stop_id)

        departures = []
        for train in train_data:
            departures.append(
                {
                    ATTR_SOURCE: "irish_rail",
                    ATTR_DESTINATION: train["destination"],
                    ATTR_ORIGIN: train["origin"],
                    ATTR_DIRECTION: train["direction"],
                    ATTR_SCHEDULED_AT: (
                        self._convert_time(train["scheduled_arrival_time"])
                    ),
                    ATTR_DUE_AT: self._convert_time(train["expected_arrival_time"]),
                    ATTR_COUNTDOWN: int(train["due_in_mins"]),
                    ATTR_ROUTE: train["type"],
                    ATTR_IS_REALTIME: True,
                }
            )
        _LOGGER.debug("IR departures: %s", departures)
        return departures

    def _convert_datestamp(self, datestamp):
        return datetime.strptime(datestamp, "%d/%m/%Y %H:%M:%S")

    def update_source_dublin_bus(self, stop_id, ssl_verify):
        """Get the latest data from http://data.dublinked.ie."""

        params = {"stopid": stop_id, "format": "json"}

        response = requests.get(
            DUBLIN_BUS_RESOURCE, params, verify=ssl_verify, timeout=RTPI_TIMEOUT
        )
        if response.status_code != 200:
            raise Exception(f"HTTP status: {str(response.status_code)}")

        ## Parse returned departure JSON data
        departures = []

        db_data = response.json()
        errorcode = str(db_data["errorcode"])
        if errorcode == "1":
            if db_data["numberofresults"] == 0:
                ## No results returned
                return []
        elif errorcode != "0":
            raise Exception("API returned error code " + errorcode)

        for dep in db_data["results"]:
            route = dep["route"]
            origin = dep["origin"]
            destination = dep["destination"]
            # now = datetime.now().replace(second=0, microsecond=0)
            direction = dep["direction"]
            scheduled_at = self._convert_datestamp(dep["scheduleddeparturedatetime"])
            due_at = self._convert_datestamp(dep["departuredatetime"])
            countdown = dep["departureduetime"]

            departures.append(
                {
                    ATTR_SOURCE: "dublin_bus",
                    ATTR_ROUTE: route,
                    ATTR_DESTINATION: destination,
                    ATTR_ORIGIN: origin,
                    ATTR_DIRECTION: direction,
                    ATTR_SCHEDULED_AT: scheduled_at,
                    ATTR_DUE_AT: due_at,
                    ATTR_COUNTDOWN: int(countdown) if countdown != "Due" else 0,
                    ATTR_IS_REALTIME: True,
                }
            )
        return departures

    def fast_update(self, current_departures):
        """Perform fast update by aging cached departure data."""
        now = datetime.now()
        departures = []
        for dep in current_departures:
            countdown = (dep[ATTR_DUE_AT] - now).total_seconds()
            if countdown >= -60 and countdown < 60:
                dep[ATTR_COUNTDOWN] = 0
                departures.append(dep)
                _LOGGER.debug(f"Departure @ {dep[ATTR_DUE_AT]} is due")
            elif countdown >= 60:
                dep[ATTR_COUNTDOWN] = int(round(countdown / 60))
                departures.append(dep)
                _LOGGER.debug(
                    f"Departure @ {dep[ATTR_DUE_AT]} due in "
                    f"{dep[ATTR_COUNTDOWN]} min"
                )
            else:
                _LOGGER.debug(f"Departure @ {dep[ATTR_DUE_AT]} aged out")
        return departures

    def update(self):
        """Get the latest data from the data source."""
        _LOGGER.info(f"Refreshing data for stop {self._stop_id}")
        self._next_refresh -= 1
        self._scan_count -= 1
        if self._next_refresh > 0:
            if self._departures:
                stop_id = self._rtpi_sources[self._current_source][CONF_STOP_ID]
                now = datetime.now()
                countdown = int(
                    round((self._departures[0][ATTR_DUE_AT] - now).total_seconds() / 60)
                )
                if countdown > self._fast_refresh_threshold:
                    _LOGGER.info(
                        f"Next departure in {countdown} min " "(outside fast refresh)"
                    )
                    ## Force fast refresh, ignore scan count
                    self._scan_count = self._next_refresh
                else:
                    _LOGGER.info(
                        f"Next departure in {countdown} min " "(within fast refresh)"
                    )
                    ## Force full refresh, modulo scan count
                    self._next_refresh = 0
            else:
                ## No unfiltered departures, or no departures
                _LOGGER.info(
                    "No data, skipping refresh " f"(refresh in {self._next_refresh}"
                )
                return True

        ## Retrieve departures for sources, using first available source
        if self._next_refresh <= 0 and self._scan_count <= 0:
            for source in self._rtpi_sources:
                source_data = self._rtpi_sources[source]
                stop_id = source_data[CONF_STOP_ID]
                skip_no_results = source_data[CONF_SKIP_NO_RESULTS]
                ssl_verify = source_data[CONF_SSL_VERIFY]
                _LOGGER.info(
                    f"Retrieving source {source} (stop_id={stop_id}, "
                    f"skip_no_results={skip_no_results}, "
                    f"ssl_verify={ssl_verify})"
                )
                try:
                    if source == RTPI_SOURCE_TFI_EFA_XML:
                        departures = self.update_source_tfi_efa_xml(stop_id, ssl_verify)
                    elif source == RTPI_SOURCE_TFI_EFA:
                        departures = self.update_source_tfi_efa(stop_id, ssl_verify)
                    elif source == RTPI_SOURCE_IRISH_RAIL:
                        ir_api = source_data[RTPI_SOURCE_IRISH_RAIL]
                        direction = source_data[CONF_DIRECTION]
                        departures = self.update_source_irish_rail(
                            ir_api, stop_id, direction, ssl_verify
                        )
                    elif source == RTPI_SOURCE_DUBLIN_BUS:
                        departures = self.update_source_dublin_bus(stop_id, ssl_verify)
                    else:
                        raise Exception(f"{stop_id}: unimplemented source {source}")
                    if departures == [] and skip_no_results:
                        if not source_data[ATTR_SOURCE_WARNING]:
                            _LOGGER.warning(
                                f"{stop_id}: ignoring empty source {source}"
                            )
                            source_data[ATTR_SOURCE_WARNING] = True
                    elif departures != None:
                        ## Departure data retrieved from current source
                        if self._current_source and self._current_source != source:
                            _LOGGER.warning(
                                f"{stop_id}: switching source from "
                                f"{self._current_source} to {source}"
                            )
                        else:
                            _LOGGER.info(f"{stop_id}: using data from source {source}")
                        self._all_departures = departures
                        self._current_source = source
                        source_data[ATTR_SOURCE_WARNING] = False
                        break
                except Exception as e:
                    departures = None
                    if not source_data[ATTR_SOURCE_WARNING]:
                        _LOGGER.warning(
                            f"{stop_id}: error retrieving data for "
                            f"source {source}: {str(e)}"
                        )
                        source_data[ATTR_SOURCE_WARNING] = True

            if departures == None:
                if self._all_departures:
                    if not self._source_warning:
                        _LOGGER.warning(
                            f"{self._stop_id}: no available data "
                            "sources, using cached data"
                        )
                        self._source_warning = True
                    self._all_departures = self.fast_update(self._all_departures)
                else:
                    _LOGGER.error(f"{self._stop_id}: no data sources")
                    return False
            else:
                self._source_warning = False
        else:
            ## Perform fast refresh
            _LOGGER.info(
                f"{self._stop_id}: Performing fast update "
                f"(next_refresh={self._next_refresh}, "
                f"scan_count={self._scan_count})"
            )
            self._all_departures = self.fast_update(self._all_departures)

        ## Regenerate filtered departure results
        self._departures = []
        self._next_departure = None
        departure_count = 0

        source = self._current_source
        source_data = self._rtpi_sources[source]
        direction = source_data[CONF_DIRECTION]
        direction_inverse = source_data[CONF_DIRECTION_INVERSE]
        realtime_only = source_data[CONF_REALTIME_ONLY]
        limit_time_horizon = self._limit_time_horizon
        limit_departures = self._limit_departures
        route = source_data[CONF_ROUTE]
        route_list = source_data[CONF_ROUTE_LIST]
        if route_list == [] and route != "":
            route_list = [route]

        _LOGGER.debug(
            f"Filter: realtime_only: {realtime_only}, "
            f"route_list: {route_list}, direction: {direction} "
            f"(inverse: {direction_inverse}), "
            f"limit_time_horizon: {limit_time_horizon}, "
            f"limit_departures: {limit_departures}"
        )
        for dep_entry in self._all_departures:
            dep_route = dep_entry[ATTR_ROUTE]
            dep_direction = dep_entry[ATTR_DIRECTION]
            dep_due_at = dep_entry[ATTR_DUE_AT]
            dep_countdown = dep_entry[ATTR_COUNTDOWN]
            dep_is_realtime = dep_entry[ATTR_IS_REALTIME]

            if (
                (not realtime_only or dep_is_realtime)
                and (not route_list or dep_route in route_list)
                and (
                    (not direction)
                    or ((not direction_inverse) and dep_direction in direction)
                    or (direction_inverse and not (dep_direction in direction))
                )
                and (dep_countdown >= 0)
                and (limit_time_horizon == 0 or dep_countdown <= limit_time_horizon)
                and (limit_departures == 0 or departure_count < limit_departures)
            ):
                _LOGGER.debug(
                    "Added departure for "
                    f"{dep_route}({dep_direction}) @ {dep_due_at} "
                    f"({dep_countdown} min) (is_realtime={dep_is_realtime})"
                )
                self._departures.append(dep_entry)
                departure_count += 1
            else:
                _LOGGER.debug(
                    "Filtered departure for "
                    f"{dep_route}({dep_direction}) @ {dep_due_at} "
                    f"({dep_countdown} min) (is_realtime={dep_is_realtime})"
                )
                pass
            if not self._next_departure:
                self._next_departure = dep_entry

        ## Determine next refresh cycle
        if self._next_refresh <= 0 and self._scan_count <= 0:
            scan_multipler = int(round(60 / SCAN_INTERVAL.total_seconds()))
            if scan_multipler < 1:
                scan_multipler = 1
            self._next_refresh = self._refresh_interval * scan_multipler
            self._scan_count = scan_multipler
            if self._departures:
                ## Upcoming unfiltered departures, use normal refresh period
                self._no_data_count = 0
            elif self._next_departure:
                ## No unfiltered departures but received filtered departures
                if self._next_departure[ATTR_COUNTDOWN] > limit_time_horizon:
                    self._next_refresh = (
                        self._next_departure[ATTR_COUNTDOWN] - limit_time_horizon
                    ) * scan_multipler
                else:
                    ## Next departure within time horizon, use normal refresh period
                    pass
            else:
                ## No unfiltered or filtered departures
                self._no_data_count += 1
                if self._no_data_count > 2:
                    self._next_refresh = self._no_data_refresh_interval * scan_multipler
                else:
                    ## No data received less than twice, use normal refresh period
                    pass

        return True
