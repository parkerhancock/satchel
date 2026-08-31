# MCP Directory Submission Reference

This independently authored checklist helps prepare an Anthropic Connectors
Directory submission. It does not reproduce or replace Anthropic's live form.
Review and answer the current form when submitting:

https://docs.google.com/forms/d/e/1FAIpQLSeafJF2NDI7oYx1r8o0ycivCSVLNq92Mpc1FPxMKSw1CzDkqA/viewform

Requirements can change after this package is released. Treat the live form,
Anthropic's submission documentation, and Anthropic's directory policies as
controlling.

## Organization and Contact

- Organization name and public website
- Primary contact name, role, and email address
- Relevant Anthropic contact, if one already exists

## Connector Listing

- Connector name and short public description
- Public MCP endpoint and product website
- Privacy, terms, support, and documentation URLs
- Category, logo, favicon, and optional promotional material
- Geographic availability and any eligibility restrictions

## Authentication and Test Access

- Authentication model, including OAuth details when applicable
- Browser authentication and CORS behavior
- Test-account instructions and non-sensitive sample data
- Expected lifetime and renewal process for reviewer access

Do not put production credentials or customer data in Satchel source files.
Provide test credentials only through the submission channel requested by
Anthropic.

## Tools, Prompts, and Resources

- Human-readable inventory of exposed tools, prompts, and resources
- Safety annotations for read-only and destructive behavior
- Representative prompts and expected outcomes
- Response-size and error-handling behavior
- Any associated Agent Skills and their intended use

## Data and Risk

- Data sources and whether the connector reads or changes third-party data
- Endpoint ownership and upstream-service relationships
- Personal, confidential, regulated, or high-risk data handled
- Retention, logging, subprocessors, and user-deletion behavior
- Financial, healthcare, legal, or other high-impact functionality

## Submission Requirements Checklist

- [ ] The production endpoint uses HTTPS and the supported remote MCP transport.
- [ ] Authentication, browser redirects, and CORS have been tested end to end.
- [ ] Tool names, titles, descriptions, and safety annotations are complete.
- [ ] Errors are actionable and responses are appropriately bounded.
- [ ] Privacy, terms, support, and documentation pages are publicly reachable.
- [ ] Branding and artwork are owned or licensed for directory use.
- [ ] Test access contains no real customer information or production secrets.
- [ ] The connector has been exercised in current Claude surfaces.
- [ ] The live submission form and directory policies were reviewed immediately
      before submission.

Record connector-specific answers in the generated
`connector-submission.md`; use the live form for the actual submission.
