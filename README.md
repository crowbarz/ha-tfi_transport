# ha-tfi_transport

Support for Dublin Bus, Irish Rail and [Transport for Ireland Journey Planner](https://journeyplanner.transportforireland.ie/) RTPI information sources to display departure board information.

* The Dublin Bus RTPI code is based on the
[Dublin Bus Transport](https://www.home-assistant.io/integrations/dublin_bus_transport)
component (though this component no longer functions as the data source has been replaced by [GTFS-RT data source](https://www.transportforireland.ie/transitData/PT_Data.html) - this source is not supported by the integration.)
* The Irish Rail RTPI code is based on the
[Irish Rail Transport](https://www.home-assistant.io/integrations/irish_rail_transport/)[pyirishrail](https://github.com/ttroy50/pyirishrail)
API frontend. This code was last updated 2017.
* The Transport for Ireland RTPI system currently uses the
[EFA Journey Planner](https://www.mentz.net/en/verkehrsauskunft/efa-journey-planner/)
system on the backend. Examples from other projects on the internet that use
call the EFA API, such as
[openefa](https://code.google.com/archive/p/openefa/)
and [metaEFA](https://github.com/opendata-stuttgart/metaEFA),
have been used to derive queries that are supported by the TFI EFA installation.

Whilst Dublin Bus and Irish Rail RTPI APIs are generally more accurate than the TFI RTPI source, both have been known to break for days on end.
To alleviate this issue, this integration supports the use of a secondary
RTPI source in case the primary RTPI source fails to respond or responds with
no data. The TFI RTPI source can be used for this purpose.

Upon refresh, a list of departures is available for use by templates in the `departures` attribute of the sensor.
Additionally, departures may be rendered in a variety of formats selectable by the `show_options` option.

## `configuration.yaml` options

To configure this component, add a separate sensor for each transit stop.

The following options are available. Configure under `sensor`:

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| `platform` | string | | Set to `tfi_transport` to use this integration for the `sensor` entity.
| `name` | string | | The display name for the transit stop
| `stop_id` | string | | _Deprecated:_ The data source specific reference ID for the transit stop. This should now be defined within the data source object.
| `limit_departures` | int | | Maximum number of departures to show.
| `limit_time_horizon` | int | | Show only departures leaving within this time (in minutes)
| `refresh_interval` | int | 1 | Time between departures board refreshes (in minutes).
| `no_data_refresh_interval` | int | 60 | Time between departures board refreshes (in minutes) if there is no data retrieved and cached data has timed out.
| `fast_refresh_threshold` | int | | Refresh every minute if there are departures due within this threshold (in minutes).
| `rtpi_sources` | object | | RTPI data sources defined for this transit stop. See [`rtpi_sources` object](#rtpi_sources-object).
| `show_options` | list | all |

## `rtpi_sources` object

Define separate objects under `rtpi_sources` for each RTPI data source that can provide departure information for the transit stop. The sources are checked in the order that they are specified and the first source for which data is available is used.

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| `stop_id` | string | from parent | The data source specific reference ID for the transit stop.
| `route` | int | | Show only this route in the returned results. Useful only for `dublin_bus`, `tfi_efa` and `tfi_efa_xml` data sources.
| `route_list` | list | | Show only these routes in the returned results. Used only by the `dublin_bus`, `tfi_efa` and `tfi_efa_xml` data sources.
| `direction` | list | | For train stops, show only departures that are heading in this direction. Used only by the `irish_rail`, `tfi_efa` and `tfi_efa_xml` data sources.
| `direction_inverse` | bool | `false` | Show only departures _not_ heading in the direction defined by `direction`.
| `realtime_only` | bool | `false` | Show only results that are flagged as real-time results.
| `skip_no_results` | bool | `false` | Use the next data source if the query is successful but no departures are returned.
| `ssl_verify` | bool | `true` | Verify SSL certificate for data source.

## `show_options`

Multiple departure rendering options may be specified simultaneously.

| Name | Description
| ---- | -----------
| `departures_text` | Render departures as text in attribute `departures_text`.
| `departures_html` | Render departures as HTML in attribute `departures_html`.
| `departures_md` | Render departures as markdown in attribute `departures_md`.
| `departures_json` | Render departures as JSON in attribute `departures_json`.
| `scheduled_at` | Show scheduled time for departure. Not supported by all data sources, in this case `scheduled_at` is identical to `due_at`.
| `due_at` | Show current estimated time for departure.
| `second_departure` | Render 2nd departure in `second_departure`
| `show_route` | Show departure route number when rendering
| `show_realtime` | Show whether departure is a real-time departure when rendering

### Stop IDs

The `stop_id` is dependent on the platform

* `dublin_bus`: use the bus stop ID for `stop_id` as found on the [Dublin Bus website](https://www.dublinbus.ie/).
* `irish_rail`: use the station name as described on the [Irish Rail API information page](https://api.irishrail.ie/realtime/).
* `tfi_efa_xml`: use the stop ID as found on the [TFI Journey Planner](https://journeyplanner.transportforireland.ie/).

## Example configuration

```yaml
## sensor.yaml configuration
- platform: tfi_transport
    name: "Buses South"
    limit_departures: 5
    limit_time_horizon: 60
    refresh_interval: 5
    fast_refresh_threshold: 5
    rtpi_sources:
      ## Deprecated as Dublin Bus stopped publishing data
      # dublin_bus:
      #   stop_id: "273"
      #   ssl_verify: false
      #   skip_no_results: true
      tfi_efa_xml:
        stop_id: "O'Connell Bridge, stop 273"
        ssl_verify: false  ## https://journeyplanner.transportforireland.ie intermediate cert not recognised
        # realtime_only: true
```
