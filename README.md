# ha-tfi_transport

Support for Dublin Bus, Irish Rail and Transport for Ireland Journey Planner
(https://journeyplanner.transportforireland.ie/) RTPI information sources.

The Dublin Bus RTPI code is based on the
[Dublin Bus Transport](https://www.home-assistant.io/integrations/dublin_bus_transport)
component.  
The Irish Rail RTPI code is based on the
[Irish Rail Transport](https://www.home-assistant.io/integrations/irish_rail_transport/)
component, which uses the
[pyirishrail](https://github.com/ttroy50/pyirishrail)
API frontend.  
The Transport for Ireland RTPI system currently uses the
[EFA Journey PLanner](https://www.mentz.net/en/verkehrsauskunft/efa-journey-planner/)
system on the backend. Examples from other projects on the internet that use
call the EFA API, such as
[openefa](https://code.google.com/archive/p/openefa/)
and [metaEFA](https://github.com/opendata-stuttgart/metaEFA),
have been used to derive queries that are supported by the TFI EFA installation.

Whilst I have found them generally more accurate than the TFI RTPI source, both
the Dublin Bus and Irish Rail RTPI APIs have been known to break for days
on end. To alleviate this issue, this component supports the use of a secondary
RTPI source in case the primary RTPI source fails to respond or responds with
no data. The TFI RTPI source can be used for this purpose.
