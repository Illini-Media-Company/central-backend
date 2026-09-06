import unittest
from unittest.mock import patch

from flask import Flask

from util.google_analytics import normalize_run_report
from views import advertiser_metrics


class AdvertiserMetricsRoutesTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.register_blueprint(advertiser_metrics.advertiser_metrics_api_routes)
        self.client = app.test_client()

    def test_sites_is_public_json_with_cors(self):
        response = self.client.get(
            "/api/advertiser-metrics/sites",
            headers={"Origin": "http://127.0.0.1:5173"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            "http://127.0.0.1:5173",
        )
        self.assertEqual(
            {site["site"] for site in response.get_json()["sites"]},
            {"daily-illini", "wpgu", "chambana-eats", "imc", "illio"},
        )

    def test_invalid_site_and_range_are_rejected(self):
        invalid_site = self.client.get(
            "/api/advertiser-metrics/overview?site=unknown&range=30d"
        )
        invalid_range = self.client.get(
            "/api/advertiser-metrics/overview?site=daily-illini&range=all"
        )

        self.assertEqual(invalid_site.status_code, 400)
        self.assertEqual(invalid_site.get_json(), {"error": "Invalid site."})
        self.assertEqual(invalid_range.status_code, 400)
        self.assertEqual(invalid_range.get_json(), {"error": "Invalid range."})

    def test_coming_soon_site_does_not_query_google_analytics(self):
        with patch.object(advertiser_metrics, "run_ga4_report") as run_report:
            response = self.client.get(
                "/api/advertiser-metrics/overview?site=imc&range=7d"
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["has_data"])
        self.assertEqual(response.get_json()["rows"], [])
        run_report.assert_not_called()

    @patch.object(advertiser_metrics, "json_store_set")
    @patch.object(advertiser_metrics, "json_store_get", return_value=None)
    def test_overview_normalizes_and_caches_ga4_metrics(self, _cache_get, cache_set):
        ga4_response = {
            "metricHeaders": [
                {"name": "screenPageViews"},
                {"name": "activeUsers"},
                {"name": "sessions"},
                {"name": "engagementRate"},
                {"name": "averageSessionDuration"},
            ],
            "rows": [
                {
                    "metricValues": [
                        {"value": "1250"},
                        {"value": "800"},
                        {"value": "925"},
                        {"value": "0.62"},
                        {"value": "74.5"},
                    ]
                }
            ],
        }

        with patch.object(
            advertiser_metrics, "run_ga4_report", return_value=ga4_response
        ) as run_report:
            response = self.client.get(
                "/api/advertiser-metrics/overview?site=daily-illini&range=30d"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["totals"],
            {
                "screenPageViews": 1250,
                "activeUsers": 800,
                "sessions": 925,
                "engagementRate": 0.62,
                "averageSessionDuration": 74.5,
            },
        )
        self.assertEqual(run_report.call_args.kwargs["property_id"], "335296694")
        cache_set.assert_called_once()

    @patch.object(advertiser_metrics, "json_store_set")
    @patch.object(advertiser_metrics, "json_store_get", return_value=None)
    def test_detail_reports_match_the_frontend_contract(self, _cache_get, _cache_set):
        report_cases = [
            (
                "timeseries",
                {
                    "dimensionHeaders": [{"name": "date"}],
                    "metricHeaders": [
                        {"name": "screenPageViews"},
                        {"name": "activeUsers"},
                        {"name": "sessions"},
                    ],
                    "rows": [
                        {
                            "dimensionValues": [{"value": "20260830"}],
                            "metricValues": [
                                {"value": "100"},
                                {"value": "70"},
                                {"value": "80"},
                            ],
                        }
                    ],
                },
                {
                    "date": "2026-08-30",
                    "screenPageViews": 100,
                    "activeUsers": 70,
                    "sessions": 80,
                },
            ),
            (
                "top-pages",
                {
                    "dimensionHeaders": [
                        {"name": "pagePath"},
                        {"name": "pageTitle"},
                    ],
                    "metricHeaders": [
                        {"name": "screenPageViews"},
                        {"name": "activeUsers"},
                        {"name": "sessions"},
                    ],
                    "rows": [
                        {
                            "dimensionValues": [
                                {"value": "/news/story"},
                                {"value": "Campus story"},
                            ],
                            "metricValues": [
                                {"value": "321"},
                                {"value": "200"},
                                {"value": "240"},
                            ],
                        }
                    ],
                },
                {
                    "pagePath": "/news/story",
                    "pageTitle": "Campus story",
                    "screenPageViews": 321,
                    "activeUsers": 200,
                    "sessions": 240,
                },
            ),
            (
                "referrers",
                {
                    "dimensionHeaders": [{"name": "sessionSourceMedium"}],
                    "metricHeaders": [
                        {"name": "sessions"},
                        {"name": "activeUsers"},
                    ],
                    "rows": [
                        {
                            "dimensionValues": [{"value": "google / organic"}],
                            "metricValues": [
                                {"value": "70"},
                                {"value": "60"},
                            ],
                        }
                    ],
                },
                {
                    "sourceMedium": "google / organic",
                    "sessions": 70,
                    "activeUsers": 60,
                },
            ),
        ]

        for endpoint, ga4_response, expected_row in report_cases:
            with self.subTest(endpoint=endpoint), patch.object(
                advertiser_metrics, "run_ga4_report", return_value=ga4_response
            ):
                response = self.client.get(
                    f"/api/advertiser-metrics/{endpoint}?site=daily-illini&range=30d"
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["rows"], [expected_row])

    @patch.object(advertiser_metrics, "json_store_set")
    @patch.object(advertiser_metrics, "json_store_get", return_value=None)
    def test_referrers_fetch_every_ga4_page(self, _cache_get, _cache_set):
        def response(rows):
            return {
                "rowCount": 3,
                "dimensionHeaders": [{"name": "sessionSourceMedium"}],
                "metricHeaders": [
                    {"name": "sessions"},
                    {"name": "activeUsers"},
                ],
                "rows": [
                    {
                        "dimensionValues": [{"value": source_medium}],
                        "metricValues": [
                            {"value": str(sessions)},
                            {"value": str(active_users)},
                        ],
                    }
                    for source_medium, sessions, active_users in rows
                ],
            }

        pages = [
            response(
                [
                    ("google / organic", 70, 60),
                    ("(direct) / (none)", 30, 25),
                ]
            ),
            response([("newsletter / email", 10, 8)]),
        ]

        with patch.object(advertiser_metrics, "REFERRER_PAGE_SIZE", 2), patch.object(
            advertiser_metrics, "run_ga4_report", side_effect=pages
        ) as run_report:
            api_response = self.client.get(
                "/api/advertiser-metrics/referrers?site=daily-illini&range=30d"
            )

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(
            [row["sourceMedium"] for row in api_response.get_json()["rows"]],
            [
                "google / organic",
                "(direct) / (none)",
                "newsletter / email",
            ],
        )
        self.assertEqual(
            [call.kwargs["offset"] for call in run_report.call_args_list], [0, 2]
        )
        self.assertTrue(
            all(call.kwargs["limit"] == 2 for call in run_report.call_args_list)
        )

    @patch.object(advertiser_metrics, "json_store_set")
    @patch.object(advertiser_metrics, "json_store_get", return_value=None)
    def test_upstream_failures_return_a_generic_error(self, _cache_get, _cache_set):
        with patch.object(
            advertiser_metrics,
            "run_ga4_report",
            side_effect=RuntimeError("private upstream details"),
        ), patch.object(advertiser_metrics.logger, "exception"):
            response = self.client.get(
                "/api/advertiser-metrics/overview?site=daily-illini&range=30d"
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.get_json(),
            {"error": "Advertiser metrics are temporarily unavailable."},
        )
        self.assertNotIn("private upstream details", response.get_data(as_text=True))


class GoogleAnalyticsNormalizationTest(unittest.TestCase):
    def test_normalize_run_report_preserves_dimension_and_metric_types(self):
        response = {
            "dimensionHeaders": [{"name": "date"}],
            "metricHeaders": [
                {"name": "screenPageViews"},
                {"name": "engagementRate"},
            ],
            "rows": [
                {
                    "dimensionValues": [{"value": "20260830"}],
                    "metricValues": [{"value": "42"}, {"value": "0.5"}],
                }
            ],
        }

        self.assertEqual(
            normalize_run_report(response),
            [
                {
                    "dimensions": {"date": "20260830"},
                    "metrics": {"screenPageViews": 42, "engagementRate": 0.5},
                }
            ],
        )

    @patch("util.security.get_creds", return_value=object())
    @patch("googleapiclient.discovery.build")
    def test_run_report_sends_limit_and_offset(self, build, _get_creds):
        service = build.return_value
        service.properties.return_value.runReport.return_value.execute.return_value = {}

        from util.google_analytics import run_ga4_report

        run_ga4_report(
            property_id="123",
            date_range={"start_date": "2026-08-01", "end_date": "2026-08-31"},
            dimensions=["sessionSourceMedium"],
            metrics=["sessions"],
            limit=100,
            offset=200,
        )

        request_body = service.properties.return_value.runReport.call_args.kwargs[
            "body"
        ]
        self.assertEqual(request_body["limit"], 100)
        self.assertEqual(request_body["offset"], 200)


if __name__ == "__main__":
    unittest.main()
