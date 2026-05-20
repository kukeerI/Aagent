#!/usr/bin/env python3
"""
Google AI Studio Rate Limit Monitor for Free Tier
================================================
Monitors and respects Google's free tier rate limits:
- 1500 requests per day (approx)
- 60 requests per minute
- ~$20 credit limit (free tier)

Usage: Add to your cron or use with model_router.py
"""

import time, json, os, logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class GoogleRateLimitMonitor:
    """Monitors and enforces Google AI Studio rate limits."""
    
    def __init__(self):
        self.google_requests_today = 0
        self.last_request_time = datetime.min
        self.max_requests_per_minute = 60
        self.daily_limit = 1500  # Approximate free tier limit
        self.credit_limit = 20.0   # $20 free credit
        
    def _parse_google_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse Google API response for rate limit headers."""
        try:
            data = json.loads(response)
            if 'meta' in data and 'usageInfo' in data['meta']:
                usage_info = data['meta']['usageInfo']
                return {
                    'total_tokens': usage_info.get('totalTokens', 0),
                    'prompt_tokens': usage_info.get('promptTokens', 0),
                    'completion_tokens': usage_info.get('completionTokens', 0),
                    'total_billed_tokens': usage_info.get('totalBilledTokens', 0),
                }
        except (json.JSONDecodeError, KeyError):
            return None
        return None

    def check_rate_limit(self) -> tuple[bool, str]:
        """
        Check if we're within rate limits.
        Returns: (allowed, message)
        """
        current_time = datetime.now()
        one_minute_ago = current_time - timedelta(minutes=1)

        # Reset daily counter at midnight (UTC+8 for China)
        china_midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=8)
        if current_time > china_midnight:
            self.google_requests_today = 0

        # Check per-minute rate limit (60 req/min for free tier)
        requests_in_minute = sum(1 for t in self._get_request_history() if t > one_minute_ago)
        if requests_in_minute >= self.max_requests_per_minute:
            wait_time = (60 - (current_time.replace(second=0, microsecond=0).timestamp() % 60)) / 60
            return False, f"Rate limited: {requests_in_minute}/{self.max_requests_per_minute} req/min. Wait ~{wait_time:.1f}s"

        # Check daily limit (approximate)
        if self.google_requests_today >= self.daily_limit:
            return False, f"Daily limit reached: {self.google_requests_today}/{self.daily_limit} requests"

        # Return allowed with current usage stats
        return True, f"OK: {requests_in_minute}/{self.max_requests_per_minute} req/min (today: {self.google_requests_today}/{self.daily_limit})"

    def _get_request_history(self) -> list[datetime]:
        """Get request history from memory or file."""
        # In production, persist this to ~/.hermes/google_rate_limit.log
        history = getattr(self, '_request_history', [])
        return [h for h in history if (datetime.now() - h).total_seconds() < 86400]  # Last 24 hours

    def record_request(self):
        """Record a request for rate limit tracking."""
        self.google_requests_today += 1
        self.last_request_time = datetime.now()
        # In production, persist to file:
        # with open("~/.hermes/google_rate_limit.log", 'a') as f:
        #     f.write(f"{datetime.now().isoformat()}")

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return {
            'requests_today': self.google_requests_today,
            'max_per_minute': self.max_requests_per_minute,
            'daily_limit': self.daily_limit,
            'credit_used': getattr(self, 'credits_used', 0),
            'last_request_time': str(self.last_request_time),
        }


def main():
    """Demo the rate limit monitor."""
    monitor = GoogleRateLimitMonitor()
    
    # Simulate some requests
    print("="*60)
    print("Google AI Studio Rate Limit Monitor - Demo")
    print("="*60 + "\n")

    for i in range(20):
        allowed, message = monitor.check_rate_limit()
        if not allowed:
            break
        monitor.record_request()
        
        # Simulate a request being made
        stats = monitor.get_usage_stats()
        print(f"Request #{i+1:2d} | Status: {message[:50]}... (today: {stats['requests_today']}/{stats['daily_limit']})")
        time.sleep(0.1)  # Small delay to avoid real rate limiting

    print("\nFinal stats:")
    for key, value in monitor.get_usage_stats().items():
        print(f"  {key}: {value}")

if __name__ == '__main__':
    main()
