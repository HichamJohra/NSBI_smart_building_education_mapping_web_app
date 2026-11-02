/* Custom cell renderers for dash-ag-grid (auto-loaded by Dash from ./assets).
   ExternalLink: shows a URL cell as a short link opening in a new tab. The cell value stays the raw URL,
   so sorting, filtering and the CSV export use the full address. */
var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

dagcomponentfuncs.ExternalLink = function (props) {
  if (!props.value) {
    return null;
  }
  return React.createElement(
    "a",
    { href: props.value, target: "_blank", rel: "noopener noreferrer", title: props.value },
    "Open ↗"
  );
};
