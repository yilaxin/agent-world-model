from __future__ import annotations

import unittest

from agent_world_model.reactive_agent import (
    ReactiveAgent,
    _extract_product_phrase,
    _extract_forum_query,
    parse_elements,
)


def state(goal: str, axtree: str, url: str = "") -> dict:
    return {"goal": goal, "url": url, "axtree": {"text": axtree}}


class ReactiveAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = ReactiveAgent()

    def test_element_parser(self) -> None:
        elements = parse_elements("[13] button 'Click Me!', clickable")
        self.assertEqual(elements[0].bid, "13")
        self.assertEqual(elements[0].role, "button")
        self.assertEqual(elements[0].name, "Click Me!")

    def test_click(self) -> None:
        decision = self.agent.decide(
            state("Click the Submit button.", "[7] button 'Submit', clickable")
        )
        self.assertEqual(decision.action_type, "click")
        self.assertEqual(decision.action, 'click("7", "left")')

    def test_input(self) -> None:
        decision = self.agent.decide(
            state(
                'Enter "phase-one-ok" into the Phase one text field.',
                "[21] textbox 'Phase one text'",
            )
        )
        self.assertEqual(decision.action_type, "input")
        self.assertEqual(decision.action, 'fill("21", "phase-one-ok")')

    def test_scroll_and_back(self) -> None:
        scroll = self.agent.decide(state("Scroll down.", "RootWebArea 'Demo'"))
        back = self.agent.decide(
            state("Go back to the previous page.", "RootWebArea 'Demo'")
        )
        self.assertEqual(scroll.action, "scroll(0, 600)")
        self.assertEqual(back.action, "go_back()")

    def test_direct_answer_uses_evaluator_action(self) -> None:
        decision = self.agent.decide(
            state("Answer the question.", "RootWebArea 'Demo'"),
            direct_answer="0",
        )
        self.assertEqual(decision.action_type, "answer")
        self.assertEqual(decision.action, 'send_msg_to_user("0")')

    def test_forum_retrieval_uses_search_then_submit(self) -> None:
        current = {
            "goal": "Find the latest post on the Showerthoughts forum.",
            "url": "http://reddit.local/",
            "axtree": {
                "text": (
                    "RootWebArea 'Postmill'\n"
                    "  [54] searchbox 'Search query', clickable\n"
                    "  [42] link 'Forums', clickable"
                )
            },
        }
        first = self.agent.decide(current)
        self.assertEqual(first.action, 'fill("54", "Showerthoughts")')
        second = self.agent.decide(current, (first.action,))
        self.assertEqual(second.action, 'keyboard_press("Enter")')

    def test_forum_search_requires_exact_forum_link_name(self) -> None:
        current = {
            "goal": 'Open a trending post on the forum "books" and subscribe.',
            "url": "http://reddit.local/search?q=books",
            "axtree": {
                "text": (
                    "RootWebArea 'Search'\n"
                    "  [124] link 'A title containing books', clickable\n"
                    "  [180] link 'books', clickable"
                )
            },
        }
        decision = self.agent.decide(current)
        self.assertEqual(decision.action, 'click("180", "left")')

    def test_target_forum_subscribes_then_opens_comments_thread(self) -> None:
        current = {
            "goal": 'Open a trending post on the forum "books" and subscribe.',
            "url": "http://reddit.local/f/books",
            "axtree": {
                "text": (
                    "RootWebArea 'books'\n"
                    "  [1094] button 'Subscribe No subscribers', clickable\n"
                    "  [163] link '184 comments', clickable"
                )
            },
        }
        subscribe = self.agent.decide(current)
        self.assertEqual(subscribe.action, 'click("1094", "left")')
        current["axtree"]["text"] = (
            "RootWebArea 'books'\n"
            "  [1094] button 'Unsubscribe', clickable\n"
            "  [163] link '184 comments', clickable"
        )
        thread = self.agent.decide(current, (subscribe.action,))
        self.assertEqual(thread.action, 'click("163", "left")')

    def test_shopping_search_is_filled_then_submitted(self) -> None:
        current = state(
            'Search for "usb wifi"',
            "[386] combobox 'Search', clickable\n[391] button 'Search', clickable",
        )
        first = self.agent.decide(current)
        self.assertEqual(first.action, 'fill("386", "usb wifi")')
        second = self.agent.decide(current, (first.action,))
        self.assertEqual(second.action, 'keyboard_press("Enter")')

    def test_disabled_search_button_is_not_clicked(self) -> None:
        decision = self.agent.decide(
            state(
                'Search for "usb wifi"',
                "[386] combobox 'Search', clickable\n[391] button 'Search', disabled=True",
            )
        )
        self.assertEqual(decision.action, 'fill("386", "usb wifi")')

    def test_unrequested_logout_is_never_selected_as_generic_fallback(self) -> None:
        decision = self.agent.decide(
            state(
                "List reviewers who mention fingerprint resistance.",
                "[21] link 'Sign Out', clickable\n[22] link 'My Account', clickable",
            )
        )
        self.assertEqual(decision.action, 'click("22", "left")')

    def test_explicit_logout_remains_available(self) -> None:
        decision = self.agent.decide(
            state("Sign out of my account.", "[21] link 'Sign Out', clickable")
        )
        self.assertEqual(decision.action, 'click("21", "left")')

    def test_gitlab_todos_opens_menu_then_visible_control(self) -> None:
        first = self.agent.decide(
            state(
                "Check out my todos",
                "RootWebArea 'Projects · Dashboard · GitLab'\n"
                "  [64] button '', clickable, hasPopup='menu', expanded=False",
                "http://gitlab.local/",
            )
        )
        self.assertEqual(first.action, 'click("64", "left")')
        second = self.agent.decide(
            state(
                "Check out my todos",
                "RootWebArea 'GitLab'\n  [91] link 'To-Do List', clickable",
                "http://gitlab.local/",
            ),
            (first.action,),
        )
        self.assertEqual(second.action, 'click("91", "left")')

    def test_gitlab_navigation_terminates_only_at_observed_target_url(self) -> None:
        issues = self.agent.decide(
            state(
                "Check out the most recent open issues",
                "RootWebArea 'Issues · GitLab'",
                "http://gitlab.local/a11yproject/a11yproject.com/-/issues/?sort=created_asc&state=opened",
            )
        )
        todos = self.agent.decide(
            state(
                "Check out my todos",
                "RootWebArea 'Todos · GitLab'",
                "http://gitlab.local/dashboard/todos",
            )
        )
        public = self.agent.decide(
            state(
                "See all public projects",
                "RootWebArea 'Explore · GitLab'",
                "http://gitlab.local/explore?visibility_level=20",
            )
        )
        self.assertEqual(issues.action_type, "answer")
        self.assertEqual(todos.action_type, "answer")
        self.assertEqual(public.action_type, "answer")

    def test_gitlab_public_projects_uses_explore_then_public(self) -> None:
        explore = self.agent.decide(
            state(
                "See all public projects",
                "RootWebArea 'GitLab'\n  [264] link 'Explore', clickable",
                "http://gitlab.local/",
            )
        )
        public = self.agent.decide(
            state(
                "See all public projects",
                "RootWebArea 'Explore · GitLab'\n  [311] link 'Public', clickable",
                "http://gitlab.local/explore",
            ),
            (explore.action,),
        )
        self.assertEqual(explore.action, 'click("264", "left")')
        self.assertEqual(public.action, 'click("311", "left")')

    def test_gitlab_recent_open_issues_applies_visible_sort_until_complete(self) -> None:
        page = (
            "RootWebArea 'Issues · GitLab'\n"
            "  [596] tab 'Open 40', clickable, selected=True\n"
            "  [724] button 'Sort direction: Ascending', clickable"
        )
        initial = self.agent.decide(
            state(
                "Check out the most recent open issues",
                page,
                "http://gitlab.local/group/project/-/issues",
            )
        )
        explicit_open = self.agent.decide(
            state(
                "Check out the most recent open issues",
                page.replace("Ascending", "Descending"),
                "http://gitlab.local/group/project/-/issues/?sort=created_date&state=opened",
            ),
            (initial.action,),
        )
        complete = self.agent.decide(
            state(
                "Check out the most recent open issues",
                page,
                "http://gitlab.local/group/project/-/issues/?sort=created_asc&state=opened",
            ),
            (initial.action, explicit_open.action),
        )
        self.assertEqual(initial.action, 'click("724", "left")')
        self.assertEqual(explicit_open.action, 'click("724", "left")')
        self.assertEqual(complete.action_type, "answer")

    def test_navigation_guard_off_disables_post_fix_gitlab_completion(self) -> None:
        agent = ReactiveAgent(navigation_guard=False)
        decision = agent.decide(
            state(
                "Check out my todos",
                "RootWebArea 'Todos · GitLab'",
                "http://gitlab.local/dashboard/todos",
            )
        )
        self.assertNotEqual(decision.action_type, "answer")
        self.assertFalse(decision.navigation_guard_applied)

    def test_navigation_guard_audit_flag_is_set_on_guard_action(self) -> None:
        decision = self.agent.decide(
            state(
                "Check out my todos",
                "RootWebArea 'Todos · GitLab'",
                "http://gitlab.local/dashboard/todos",
            )
        )
        self.assertTrue(decision.navigation_guard_applied)

    def test_shopping_add_to_wishlist_search_flow(self) -> None:
        initial = self.agent.decide(
            state(
                "Add a laundry detergent to my wish list.",
                "[55] combobox 'Search', clickable\n[58] button 'Search', clickable",
                "http://localhost:7770/",
            )
        )
        self.assertEqual(initial.action, 'fill("55", "laundry detergent")')
        submitted = self.agent.decide(
            state(
                "Add a laundry detergent to my wish list.",
                "[55] combobox 'Search', clickable",
                "http://localhost:7770/",
            ),
            (initial.action,),
        )
        self.assertEqual(submitted.action, 'keyboard_press("Enter")')

    def test_shopping_product_page_adds_to_wish_list(self) -> None:
        decision = self.agent.decide(
            state(
                "Add a laundry detergent to my wish list.",
                "RootWebArea 'Laundry Detergent'\n"
                "  [90] button 'Add to Wish List', clickable\n"
                "  [91] button 'Add to Cart', clickable",
                "http://localhost:7770/laundry-detergent.html",
            )
        )
        self.assertEqual(decision.action, 'click("90", "left")')

    def test_shopping_wishlist_page_terminates_when_product_visible(self) -> None:
        decision = self.agent.decide(
            state(
                "Add a laundry detergent to my wish list.",
                "RootWebArea 'My Wish List'\n"
                "  [200] link 'Laundry Detergent', clickable",
                "http://localhost:7770/wishlist/",
            )
        )
        self.assertEqual(decision.action_type, "answer")
        self.assertEqual(decision.action, 'send_msg_to_user("Done")')

    def test_shopping_product_flow_ignored_off_shopping_host(self) -> None:
        decision = self.agent.decide(
            state(
                "Who else have access to my repo, show me their usernames",
                "[55] combobox 'Search', clickable",
                "http://localhost:8023/dashboard/projects",
            )
        )
        self.assertNotEqual(decision.action_type, "input")

    def test_shopping_contact_us_navigates_to_contact_page(self) -> None:
        decision = self.agent.decide(
            state(
                'Fill the "contact us" form in the site for a refund on the speaker.',
                "RootWebArea 'One Stop Market'\n"
                "  [90] link 'Contact Us', clickable",
                "http://localhost:7770/",
            )
        )
        self.assertEqual(decision.action, 'click("90", "left")')

    def test_shopping_order_total_opens_account_then_orders(self) -> None:
        first = self.agent.decide(
            state(
                "Tell me the total cost of my latest cancelled order?",
                "RootWebArea 'Home'\n  [221] link 'My Account', clickable",
                "http://localhost:7770/",
            )
        )
        self.assertEqual(first.action, 'click("221", "left")')
        second = self.agent.decide(
            state(
                "Tell me the total cost of my latest cancelled order?",
                "RootWebArea 'My Account'\n  [1599] link 'My Orders', clickable",
                "http://localhost:7770/customer/account/",
            ),
            (first.action,),
        )
        self.assertEqual(second.action, 'click("1599", "left")')

    def test_shopping_orders_table_answers_cancelled_total(self) -> None:
        page = (
            "RootWebArea 'My Orders'\n"
            "  [1503] table 'Orders'\n"
            "  [1507] columnheader 'Order #'\n"
            "  [1508] columnheader 'Date'\n"
            "  [1509] columnheader 'Order Total'\n"
            "  [1510] columnheader 'Status'\n"
            "  [1511] columnheader 'Action'\n"
            "  [1514] gridcell '000000170'\n"
            "  [1515] gridcell '5/17/23'\n"
            "  [1516] gridcell '$365.42'\n"
            "  [1518] gridcell 'Canceled'\n"
            "  [1519] gridcell 'View OrderReorder'\n"
            "  [1525] gridcell '000000189'\n"
            "  [1526] gridcell '5/2/23'\n"
            "  [1527] gridcell '$754.99'\n"
            "  [1529] gridcell 'Pending'\n"
            "  [1530] gridcell 'View OrderReorder'"
        )
        decision = self.agent.decide(
            state(
                "Tell me the total cost of my latest cancelled order?",
                page,
                "http://localhost:7770/sales/order/history/",
            )
        )
        self.assertEqual(decision.action_type, "answer")
        self.assertEqual(decision.action, 'send_msg_to_user("$365.42")')

    def test_reddit_reply_fills_and_submits_comment(self) -> None:
        thread = state(
            'Reply to the post with my comment "I am a big fan of the bookorg"',
            "RootWebArea 'Post'\n"
            "  [300] textbox 'Add a comment', clickable\n"
            "  [310] button 'Comment', clickable",
            "http://localhost:9999/f/books/12345",
        )
        first = self.agent.decide(thread)
        self.assertEqual(first.action, 'fill("300", "I am a big fan of the bookorg")')
        second = self.agent.decide(thread, (first.action,))
        self.assertEqual(second.action, 'click("310", "left")')

    def test_reddit_reply_opens_thread_before_commenting(self) -> None:
        decision = self.agent.decide(
            state(
                'Reply to the post with my comment "Nice"',
                "RootWebArea 'books'\n  [163] link '184 comments', clickable",
                "http://localhost:9999/f/books",
            )
        )
        self.assertEqual(decision.action, 'click("163", "left")')

    def test_subscribe_only_goal_terminates_after_unsubscribe_visible(self) -> None:
        decision = self.agent.decide(
            state(
                "Subscribe to the books forum.",
                "RootWebArea 'books'\n"
                "  [1094] button 'Unsubscribe', clickable",
                "http://reddit.local/f/books",
            )
        )
        self.assertEqual(decision.action, 'send_msg_to_user("Done")')

    def test_loop_recovery_breaks_repeated_same_bid_clicks(self) -> None:
        current = state(
            "Click the Submit button.",
            "[7] button 'Submit', clickable",
            "http://demo.local/page",
        )
        action = 'click("7", "left")'
        decision = self.agent.decide(current, (action, action, action, action))
        self.assertEqual(decision.action_type, "scroll")

    def test_timeout_recovery_scrolls_after_click_timeout(self) -> None:
        decision = self.agent.decide(
            {
                "goal": "Click the Submit button.",
                "url": "http://demo.local/page",
                "axtree": {"text": "[7] button 'Submit', clickable"},
                "last_action": 'click("7", "left")',
                "last_action_error": "Locator.click: Timeout 30000ms exceeded",
            }
        )
        self.assertEqual(decision.action_type, "scroll")

    def test_no_submit_tasks_never_terminate(self) -> None:
        decision = self.agent.decide(
            state(
                "Fill the contact us form for a refund. Don't submit yet, I will check.",
                "RootWebArea 'My Wish List'\n  [200] link 'Laundry Detergent', clickable",
                "http://shopping.local/wishlist/",
            )
        )
        self.assertNotEqual(decision.action, 'send_msg_to_user("Done")')

    def test_product_phrase_extraction_handles_vague_goals(self) -> None:
        self.assertEqual(
            _extract_product_phrase(
                "I have jaw bruxism problem, show me something that could "
                "alleviate the problem."
            ),
            "jaw bruxism",
        )
        self.assertEqual(
            _extract_product_phrase(
                "Show the least expensive ssd hard drive with a minimum "
                "storage capacity of 1TB."
            ),
            "ssd hard drive",
        )
        self.assertEqual(
            _extract_product_phrase(
                "I have a lot of Nintendo Switch game cards now, help me find "
                "the best storage option to fit all 6 cards"
            ),
            "storage",
        )

    def test_loop_recovery_runs_before_shopping_flow(self) -> None:
        current = state(
            "Add a laundry detergent to my wish list.",
            "[55] combobox 'Search', clickable\n"
            "[1509] link 'Laundry Detergent', clickable",
            "http://shopping.local/catalogsearch/result/?q=laundry+detergent",
        )
        action = 'click("1509", "left")'
        decision = self.agent.decide(
            current,
            (action, action, action, action),
        )
        self.assertEqual(decision.action_type, "scroll")

    def test_forum_query_ignores_article_in_subreddit(self) -> None:
        self.assertEqual(
            _extract_forum_query(
                "Post my question in a subreddit where I'm likely to get an answer."
            ),
            "",
        )
        self.assertEqual(
            _extract_forum_query(
                'Post in the forum "books".'
            ),
            "books",
        )


if __name__ == "__main__":
    unittest.main()
