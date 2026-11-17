# Model comparison

| Model | Field accuracy | Verdict agreement | Rule flags caught | Summary checks | Mean latency | Mean tokens | Cost / claim | Cost / 10k claims |
|---|---|---|---|---|---|---|---|---|
| nova-micro -> haiku-4.5 | 100% | 100% | 100% | 100% | 1,732 ms | 1,529 | $0.00060 | $6.03 |
| nova-lite -> haiku-4.5 | 100% | 100% | 100% | 100% | 2,370 ms | 1,580 | $0.00071 | $7.08 |
| haiku-4.5 | 100% | 100% | 100% | 100% | 2,820 ms | 2,062 | $0.00382 | $38.20 |
| nova-micro | 100% | 67% | 100% | 100% | 1,391 ms | 1,498 | $0.00008 | $0.78 |
| nova-lite | 100% | 67% | 100% | 100% | 1,819 ms | 1,527 | $0.00013 | $1.31 |

## Per-claim results

### haiku-4.5 - `claims/claim-001-auto.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **CLAIMS BRIEFING – POL-100234**
> 
> **Incident Summary**
> Maria Okafor's vehicle was struck from behind at an intersection on 14 August 2026, sustaining damage to the rear bumper, boot lid, and left tail light; the other driver admitted fault.
> 
> **Coverage Assessment**
> LIKELY COVERED. The claim involves collision with another vehicle, which falls within "Collision with another vehicle or object" under Covered Perils. The claimed amount of $3,840.50 exceeds the $2,000 threshold requiring a police report number per Claim Requirements.
> 
> **Next Actions**
> 1. Verify incident was reported within 30 days of 14 August 2026
> 2. Request police report number (mandatory for claims above $2,000)
> 3. Obtain repair estimates and photos
> 4. Confirm deductible amount and apply to settlement
> 5. Authorize repairs through approved repair shop once documentation is complete

### haiku-4.5 - `claims/claim-002-home.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **CLAIMS BRIEFING**
> 
> **Claimant:** James Whitfield | **Policy:** POL-200871 | **Claim Amount:** $4,250.00
> 
> **Incident:** Supply pipe under kitchen sink burst on October 3, 2026, causing approximately one inch of water damage to the kitchen and hallway, with plumber repairs including fitting replacement, water extraction, flooring, and cabinet replacement.
> 
> **Coverage Assessment:** LIKELY COVERED. The claim involves sudden and accidental discharge of water from plumbing, which falls within "Covered Perils." The policy explicitly covers "the cost of tearing out and replacing the part of the building needed to reach the damaged system," supporting coverage for the floor and cabinet work. No exclusions apply—this was not continuous seepage or flood damage.
> 
> **Next Action:** Request itemized contractor invoices, photos of the damage, and confirmation of the discovery date to satisfy "Claim Requirements." Verify the plumber's invoice details before processing payment.

### haiku-4.5 - `claims/claim-003-travel.txt`

- Field misses: none; verdict: NEEDS REVIEW (matches expected); guardrail: GUARDRAIL_INTERVENED ['ADDRESS']
- Validation: [warning] claim_amount: 6,800.00 exceeds coverage limit 5,000.00

> **CLAIMS BRIEFING – POL-300552**
> 
> **Incident Summary**
> Claimant experienced two separate incidents during travel to {ADDRESS}: theft of suitcase during hotel check-in on 22/07/2026 and a fall on tram steps on 24/07/2026 requiring emergency hospital treatment.
> 
> **Coverage Assessment**
> NEEDS REVIEW. The claim presents two distinct coverage issues:
> 
> 1. **Baggage theft**: LIKELY COVERED under Baggage and Personal Items (max $1,500 per trip). However, police report requirement must be verified—theft must be reported within 24 hours per policy Exclusions.
> 
> 2. **Emergency medical treatment**: LIKELY COVERED under Emergency Medical for hospital treatment abroad. Requires itemised bills and treating doctor's report per policy terms.
> 
> **Critical Issue**: Total claim ($6,800) significantly exceeds combined available coverage (~$1,500 baggage + policy medical limit). Automated validation flags $5,000 coverage limit discrepancy.
> 
> **Next Action**
> Request police report for theft incident, itemised medical bills, and doctor's report. Clarify policy medical limit and confirm incident dates align with policy validity.

### nova-lite - `claims/claim-001-auto.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **Incident Description:** Maria Okafor was rear-ended at a red light, damaging her car's rear bumper, boot lid, and left tail light.
> 
> **Coverage Assessment:** LIKELY COVERED. The collision with another vehicle is covered under "Covered Perils" (POL-100234).
> 
> **Next Action:** Request a police report number, photos, and at least one repair estimate due to the repair cost exceeding $2,000, as per "Claim Requirements" (POL-100234).

### nova-lite - `claims/claim-002-home.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **Incident Description:** On 3 October 2026, a supply pipe under the kitchen sink burst while the claimant was asleep.
> 
> **Coverage Assessment:** LIKELY COVERED. The incident involves the sudden and accidental discharge of water from plumbing, which is covered under "Covered Perils" (POL-200871).
> 
> **Next Action:** Request photos, itemised contractor invoices, and the date the damage was discovered to proceed with the claim.

### nova-lite - `claims/claim-003-travel.txt`

- Field misses: none; verdict: LIKELY COVERED (differs from expected); guardrail: GUARDRAIL_INTERVENED ['ADDRESS']
- Validation: [warning] claim_amount: 6,800.00 exceeds coverage limit 5,000.00; [warning] summary: Verdict is LIKELY COVERED although rule checks raised issues

> **Incident:** Priya Raman's suitcase was stolen in {ADDRESS}, followed by a tram accident requiring hospital treatment.
> 
> **Coverage Assessment:** LIKELY COVERED. Stolen baggage is covered up to $500 under "Baggage and Personal Items" and medical treatment is covered under "Emergency Medical." However, the claim amount exceeds the policy limit. ("Baggage and Personal Items," "Emergency Medical")
> 
> **Next Action:** Review the claim amount and ensure all required documentation is submitted.

### nova-micro - `claims/claim-001-auto.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **Briefing for Claim POL-100234:**
> 
> **Incident Description:** On August 14, 2026, Maria Okafor's car was rear-ended at a junction, causing damage to the rear bumper, boot lid, and left tail light.
> 
> **Coverage Assessment:** LIKELY COVERED. The incident involves a collision with another vehicle, fitting the description under Covered Perils (POL-100234). 
> 
> **Next Action:** Request the claimant to submit a police report number due to the repair cost exceeding $2,000 and provide photos and at least one repair estimate as per Claim Requirements (POL-100234).

### nova-micro - `claims/claim-002-home.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **Incident Description:** James Whitfield reported water damage in the kitchen due to a burst supply pipe on October 3, 2026.
> 
> **Coverage Assessment:** LIKELY COVERED. The incident involves a sudden discharge of water from a burst supply pipe, which is not excluded under the policy's exclusions for wear and tear or continuous leakage. (Refer to Exclusions, POL-200871).
> 
> **Next Action for the Handler:** Request photos, itemised contractor invoices, and the date the damage was discovered to validate the claim fully. Ensure the claimant took reasonable steps to prevent further damage, such as shutting off the water supply. (Refer to Claim Requirements, POL-200871).

### nova-micro - `claims/claim-003-travel.txt`

- Field misses: none; verdict: LIKELY NOT COVERED (differs from expected); guardrail: GUARDRAIL_INTERVENED ['ADDRESS']
- Validation: [warning] claim_amount: 6,800.00 exceeds coverage limit 5,000.00

> **Incident Description:** Priya Raman's suitcase was stolen from a hotel lobby in {ADDRESS}, and she fell on tram steps requiring hospital treatment.
> 
> **Coverage Assessment:** LIKELY NOT COVERED due to the claim amount of $6,800 exceeding the coverage limit of $5,000 per trip. Additionally, the incident involves medical treatment, which is not covered under the Baggage and Personal Items section (Policy Section: Exclusions).
> 
> **Next Action for the Handler:** Contact Priya Raman to gather additional documentation to support the medical expenses, but inform her that the claim for the stolen suitcase will likely not be covered due to the coverage limit and amount exceeding the policy's terms.

### nova-micro -> haiku-4.5 - `claims/claim-001-auto.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **Briefing for Claims Handler:**
> 
> **Incident Description:** Maria Okafor was rear-ended at a red light intersection, causing damage to the rear bumper, boot lid, and left tail light.
> 
> **Coverage Assessment:** LIKELY COVERED. The incident involves a collision with another vehicle, fitting the description under Covered Perils (POL-100234). The repair cost exceeds $2,000, but no police report number was provided, which is required by Claim Requirements (POL-100234).
> 
> **Next Action:** Request a police report number and ask for photos and a repair estimate from the claimant to fulfill the Claim Requirements (POL-100234).

### nova-micro -> haiku-4.5 - `claims/claim-002-home.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **Incident Description:** James Whitfield reported water damage in the kitchen due to a burst supply pipe on October 3, 2026.
> 
> **Coverage Assessment:** LIKELY COVERED. The damage resulted from a sudden discharge of water, which is covered under the policy, barring exclusions for continuous leaks or mould not directly resulting from a sudden discharge. (Policy Section: Coverage)
> 
> **Next Action:** Request photos, itemised contractor invoices, and the date the damage was discovered to validate the claim fully. Ensure the steps taken to prevent further damage are documented.

### nova-micro -> haiku-4.5 - `claims/claim-003-travel.txt`

- Field misses: none; verdict: NEEDS REVIEW (matches expected); guardrail: GUARDRAIL_INTERVENED ['ADDRESS']
- Validation: [warning] claim_amount: 6,800.00 exceeds coverage limit 5,000.00

> **CLAIMS BRIEFING – POL-300552**
> 
> **Incident Summary**
> Claimant's suitcase was stolen from a hotel lobby in {ADDRESS} on 22 July 2026, and she sustained injuries from a fall on tram steps requiring hospitalization.
> 
> **Coverage Assessment**
> NEEDS REVIEW. The baggage theft claim of $6,800 significantly exceeds policy limits under *Baggage and Personal Items*, which covers lost or stolen baggage up to $1,500 per trip with a $500 maximum per single item. The claim is valid only if a police report was filed within 24 hours as required by the *Baggage and Personal Items* section. The medical claim from the tram fall falls outside baggage coverage and requires separate assessment against medical/accident provisions not provided here.
> 
> **Next Action**
> Request police report documentation from claimant to verify theft was reported within 24 hours. Clarify whether the $6,800 represents baggage value only or includes medical expenses. Obtain itemized baggage list and medical records for the tram incident.

### nova-lite -> haiku-4.5 - `claims/claim-001-auto.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **Incident Description:** Maria Okafor's car was rear-ended at a red light, damaging the rear bumper, boot lid, and left tail light.
> 
> **Coverage Assessment:** LIKELY COVERED. The incident involves a collision with another vehicle, which is covered under "Covered Perils" (POL-100234).
> 
> **Next Action:** Request a police report number, photos, and at least one repair estimate as per "Claim Requirements" (POL-100234).

### nova-lite -> haiku-4.5 - `claims/claim-002-home.txt`

- Field misses: none; verdict: LIKELY COVERED (matches expected); guardrail: NONE 

> **Incident Description:** On 3 October 2026, the kitchen supply pipe burst while the claimant was asleep.
> 
> **Coverage Assessment:** LIKELY COVERED. The incident involves the sudden and accidental discharge of water from plumbing, which is explicitly covered under "Covered Perils" (POL-200871).
> 
> **Next Action:** Request photos, itemised contractor invoices, and the date the damage was discovered from the claimant.

### nova-lite -> haiku-4.5 - `claims/claim-003-travel.txt`

- Field misses: none; verdict: NEEDS REVIEW (matches expected); guardrail: NONE 
- Validation: [warning] claim_amount: 6,800.00 exceeds coverage limit 5,000.00

> **CLAIMS BRIEFING – POL-300552**
> 
> **Incident Summary**
> Claimant's suitcase was stolen from a Lisbon hotel lobby on 22 July 2026, and she subsequently sustained a tram-related injury requiring hospital treatment on 24 July.
> 
> **Coverage Assessment**
> **NEEDS REVIEW.** Two separate claims are presented. The baggage theft appears eligible under *Baggage and Personal Items* (police report provided within 24 hours as required); however, the claimed amount of $6,800 significantly exceeds the $1,500 per-trip limit. The emergency medical treatment on 24 July falls under *Emergency Medical* coverage, but requires itemised bills and treating doctor's report to validate. The validation system flags the total claim amount as exceeding policy limits.
> 
> **Next Action**
> Request itemised medical bills and doctor's report from Hospital de Santa Maria. Obtain the written police report for the theft. Separate the claims and apply appropriate limits: $1,500 maximum for baggage (less any single-item deductibles), and process medical costs within policy limits pending documentation review.
