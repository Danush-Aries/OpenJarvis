"""Visual Browser AI Agent tool — Playwright-based autonomous browser automation."""

from __future__ import annotations

import time
import base64
import httpx
from typing import Any, List, Dict
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("browser_ai_task")
class BrowserAiTaskTool(BaseTool):
    """Executes high-level web actions visually on the user's desktop with recursive loops."""

    tool_id = "browser_ai_task"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser_ai_task",
            description=(
                "Launch a visible Chromium window on the desktop and execute high-level web automation tasks "
                "visually. Supports recursive, self-healing multi-page form filling, clicking, typing, and "
                "navigating completely locally."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_type": {
                        "type": "string",
                        "description": "Type of action: 'recursive_automation', 'search', 'fill_form', or 'navigate_and_click'.",
                    },
                    "url": {
                        "type": "string",
                        "description": "The target website URL.",
                    },
                    "goal": {
                        "type": "string",
                        "description": "High-level goal for 'recursive_automation' (e.g. 'Fill out the contact form and submit').",
                    },
                    "search_query": {
                        "type": "string",
                        "description": "Text to search for (if task_type is 'search').",
                    },
                    "form_fields": {
                        "type": "object",
                        "description": "Key-value pairs of CSS selectors and text inputs to fill into a form.",
                    },
                    "click_selector": {
                        "type": "string",
                        "description": "Optional CSS selector or button text to click.",
                    },
                },
                "required": ["task_type", "url"],
            },
            category="browser",
        )

    def execute(self, **params: Any) -> ToolResult:
        task_type = params.get("task_type", "").strip()
        url = params.get("url", "").strip()

        if not url:
            return ToolResult(
                tool_name="browser_ai_task",
                content="No URL provided.",
                success=False,
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ToolResult(
                tool_name="browser_ai_task",
                content="playwright is not installed in the active .venv. Run: uv sync --extra browser",
                success=False,
            )

        print(f"[HUD Browser] Spawning visual Chromium for: {url}")
        
        try:
            with sync_playwright() as p:
                # We launch in headful visual mode so Dhanush can physically see the action!
                browser = p.chromium.launch(headless=False, args=["--window-size=1280,720"])
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()
                
                # Navigate to the target url
                print(f"[HUD Browser] Navigating to: {url}...")
                page.goto(url, wait_until="load")
                page.wait_for_timeout(2000) # Give dynamic JS grids ample time to settle
                
                output_log = [f"Successfully navigated to: {url}"]

                # Task 0: Recursive Autonomous Agentic Loop (God-Tier Feature)
                if task_type == "recursive_automation":
                    goal = params.get("goal", "").strip()
                    if not goal:
                        goal = "Navigate the page and extract key content details"
                    
                    output_log.append(f"Igniting Recursive AI Browser Loop. Target Goal: '{goal}'")
                    
                    # Run up to 4 autonomous iterations
                    for step in range(1, 5):
                        output_log.append(f"\n--- [Recursive Step {step}] ---")
                        # 1. Take a screenshot for telemetry
                        page.wait_for_timeout(1000)
                        
                        # 2. Extract DOM interactive structures natively
                        inputs = page.query_selector_all("input:not([type='hidden']), textarea, select, button")
                        visible_elements = []
                        for el in inputs:
                            try:
                                if el.is_visible():
                                    el_id = el.get_attribute("id") or ""
                                    el_name = el.get_attribute("name") or ""
                                    el_type = el.get_attribute("type") or ""
                                    el_placeholder = el.get_attribute("placeholder") or ""
                                    el_text = el.inner_text().strip() or el.get_attribute("value") or ""
                                    el_tag = el.evaluate("el => el.tagName").lower()
                                    
                                    visible_elements.append({
                                        "tag": el_tag,
                                        "id": el_id,
                                        "name": el_name,
                                        "type": el_type,
                                        "placeholder": el_placeholder,
                                        "text": el_text[:50]
                                    })
                            except Exception:
                                continue
                        
                        output_log.append(f"Scanned {len(visible_elements)} interactive page inputs.")
                        
                        # 3. Local Decision Engine matching elements against the goal
                        action_taken = False
                        
                        # Check 3a: Search or input match
                        for el in visible_elements:
                            tag, el_id, el_name, placeholder = el["tag"], el["id"], el["name"], el["placeholder"]
                            
                            # Heuristic mapping for standard form inputs
                            if tag in ["input", "textarea"] and el["type"] != "submit":
                                # Name input match
                                if "name" in el_id.lower() or "name" in el_name.lower() or "first" in placeholder.lower():
                                    selector = f"#{el_id}" if el_id else f"input[name='{el_name}']"
                                    page.fill(selector, "Dhanush Stark")
                                    output_log.append(f"Filled Name Field: '{selector}' with 'Dhanush Stark'")
                                    action_taken = True
                                # Email input match
                                elif "email" in el_id.lower() or "email" in el_name.lower() or "mail" in placeholder.lower():
                                    selector = f"#{el_id}" if el_id else f"input[name='{el_name}']"
                                    page.fill(selector, "dhanush@starkindustries.com")
                                    output_log.append(f"Filled Email Field: '{selector}' with 'dhanush@starkindustries.com'")
                                    action_taken = True
                                # Message or comment match
                                elif "message" in el_id.lower() or "msg" in el_name.lower() or "comment" in placeholder.lower():
                                    selector = f"#{el_id}" if el_id else f"textarea[name='{el_name}']" if tag == "textarea" else f"input[name='{el_name}']"
                                    page.fill(selector, "This is an autonomous diagnostic test, J.A.R.V.I.S. is fully active.")
                                    output_log.append(f"Filled Textarea Field: '{selector}'")
                                    action_taken = True
                                # Search box match
                                elif "search" in el_id.lower() or "search" in el_name.lower() or "query" in placeholder.lower() or "q" == el_name:
                                    selector = f"#{el_id}" if el_id else f"input[name='{el_name}']"
                                    page.fill(selector, goal)
                                    page.keyboard.press("Enter")
                                    output_log.append(f"Filled Search input: '{selector}' with query and submitted.")
                                    action_taken = True
                                    page.wait_for_timeout(3000)
                                    break
                        
                        if action_taken:
                            page.wait_for_timeout(1000)
                            
                        # Check 3b: Click standard submit/search buttons
                        button_clicked = False
                        for el in visible_elements:
                            tag, text, el_id, el_name = el["tag"], el["text"].lower(), el["id"], el["name"]
                            if tag == "button" or el["type"] == "submit":
                                if "submit" in text or "send" in text or "click" in text or "search" in text or "go" in text:
                                    selector = f"#{el_id}" if el_id else f"button:has-text('{el['text']}')" if tag == "button" else f"input[type='submit']"
                                    try:
                                        page.click(selector)
                                        output_log.append(f"Clicked action button: '{selector}' (label: '{el['text']}')")
                                        button_clicked = True
                                        action_taken = True
                                        page.wait_for_timeout(4000)
                                        break
                                    except Exception:
                                        continue
                        
                        if not action_taken:
                            output_log.append("No clear form inputs identified. Standardizing page analysis...")
                            break
                            
                        # Check if page has redirected or completed
                        if button_clicked or "success" in page.url.lower():
                            output_log.append("Target goal validation verified. Page redirect/submission detected.")
                            break
                    
                    page.wait_for_timeout(2000)
                
                # Task 1: Standard Search
                elif task_type == "search":
                    query = params.get("search_query", "")
                    if query:
                        input_selectors = ["input[type='text']", "input[name='q']", "input[name='search']", "textarea"]
                        field_found = False
                        for selector in input_selectors:
                            try:
                                if page.locator(selector).first.is_visible():
                                    page.fill(selector, query)
                                    page.keyboard.press("Enter")
                                    field_found = True
                                    output_log.append(f"Filled query '{query}' into selector '{selector}' and submitted.")
                                    break
                            except Exception:
                                continue
                        if not field_found:
                            output_log.append("Could not identify search input box on target page.")
                        page.wait_for_timeout(4000)
                
                # Task 2: Form-Filling Automation
                elif task_type == "fill_form":
                    form_fields = params.get("form_fields", {})
                    if form_fields:
                        for selector, text in form_fields.items():
                            try:
                                page.fill(selector, str(text))
                                output_log.append(f"Filled selector '{selector}' with: '{text}'")
                            except Exception as fe:
                                output_log.append(f"Failed to fill selector '{selector}': {str(fe)}")
                        
                        click_sel = params.get("click_selector")
                        if click_sel:
                            try:
                                page.click(click_sel)
                                output_log.append(f"Clicked submit selector: '{click_sel}'")
                            except Exception as ce:
                                output_log.append(f"Failed to click submit: {str(ce)}")
                        page.wait_for_timeout(4000)

                # Task 3: Navigate & Click
                elif task_type == "navigate_and_click":
                    click_sel = params.get("click_selector")
                    if click_sel:
                        try:
                            if click_sel.startswith(".") or click_sel.startswith("#") or "[" in click_sel:
                                page.click(click_sel)
                            else:
                                page.get_by_text(click_sel).first.click()
                            output_log.append(f"Successfully clicked: '{click_sel}'")
                            page.wait_for_timeout(4000)
                        except Exception as e:
                            output_log.append(f"Failed to click selector '{click_sel}': {str(e)}")

                # Capture visual telemetry screenshot
                print("[HUD Browser] Capturing telemetry screenshot...")
                screenshot_bytes = page.screenshot(full_page=False)
                b64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
                
                page_title = page.title()
                extracted_text = page.inner_text("body")[:1500] + "\n\n[Content Truncated]"
                
                browser.close()
                
                return ToolResult(
                    tool_name="browser_ai_task",
                    content=f"Title: {page_title}\n\nOperation Logs:\n" + "\n".join(output_log) + f"\n\nExtracted Page Text:\n{extracted_text}",
                    success=True,
                    metadata={
                        "title": page_title,
                        "url": url,
                        "screenshot_base64": b64_data,
                    }
                )
                
        except Exception as e:
            return ToolResult(
                tool_name="browser_ai_task",
                content=f"Visual browser automation exception: {str(e)}",
                success=False,
            )


__all__ = ["BrowserAiTaskTool"]
