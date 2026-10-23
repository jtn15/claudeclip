# Admin-only steps (things the theme code can't do)

Do them in this order. Each step says where to click.

## 1. Upload the updated theme
Online Store > Themes > Add theme > Upload zip file > `maisonrivault-theme.zip`. Preview it, then **Publish**.
Uploading as a new theme keeps your current live theme as a backup.

## 2. Create the Shipping and returns page (fixes the 404)
Online Store > Pages > Add page
- Title: `Shipping and returns`
- Paste the text from `content/shipping-returns-page.md`, after filling in every [FILL IN]
- Search engine listing > URL handle: `shipping-returns`
- Theme template (right column): `shipping-returns`
- Save. Then open `maisonrivault.com/pages/shipping-returns` and check it loads.

Optional: Online Store > Themes > Customize > Theme settings > Pages > "Shipping and returns page", then pick this page.
Every "Shipping and returns" link in the theme will follow it even if the handle changes later.

## 3. Footer and menus (admin-managed, not theme code)
The footer's **Help** column is the menu with handle `footer`. Its links are set in Online Store > Navigation > Footer menu, not in the theme.
The **Legal** column lists your Shopify policies automatically. The line at the very bottom of the footer is theme code, and it already points to `/pages/shipping-returns`.
Check that the Footer menu's "Shipping and returns" item points to the page from step 2. If you delete and recreate the page, re-pick it here.

## 4. Paste the policies
Settings > Policies
- **Return and refund policy:** paste `content/refund-policy.md` (fill in the date).
- **Shipping policy:** use the Shipping section of `content/shipping-returns-page.md`.
- **Contact information:** set the email to **info@maisonrivault.com**. The current refund policy's contact block says help@. Search every policy for "help@" and replace it.

## 5. Clear crossed-out prices
The "COMPARABLE VALUE" strikethrough didn't come from compare-at prices. It came from a list of made-up "comparable" prices written directly into the theme for all 8 products: Ashby $118, Beaumont $79.50, Carrington $95, Hartwell $145, Hollis $60, Lockhart $105, Sinclair $98, Whitlock $94. That list is now deleted from the theme.
The theme also no longer displays Shopify compare-at prices, so a sale strikethrough won't appear on product cards or product pages either. To clear any that are set:
Products > select all > **Bulk edit** > Columns > add **Compare-at price** > clear every cell > Save.
I can't see your product data from the theme files, so check every row. If a `custom.market_value` metafield definition exists (Settings > Custom data > Products), you can delete it too, because nothing reads it now.

## 6. Create the fit-note metafield definitions
Settings > Custom data > Products > **Add definition**, four times:

| Name | Namespace and key | Type |
|---|---|---|
| Model height | `custom.model_height` | Single line text |
| Model size worn | `custom.model_size_worn` | Single line text |
| Country of manufacture | `custom.country_of_manufacture` | Single line text |
| Shrinkage note | `custom.shrinkage_note` | Multi-line text |

Then fill them per product using `content/product-page-copy-checklist.md`. Nothing shows on the site until a field has a value.

## 7. Install a reviews app
No reviews app is installed in this theme (no app blocks or review scripts in the files you sent). **Install Judge.me** (free plan). Shopify's own Product Reviews app has been discontinued, so don't look for it.
The theme shows stars under the product title and on product cards from Shopify's standard review fields (`reviews.rating`, `reviews.rating_count`). Judge.me can write to these. After your first real review, check that the stars appear. If they don't, add Judge.me's star-rating block in the theme editor (Product page > Add block > Apps).
Stars show nothing until real reviews exist. No fake ratings or review schema were added.

## 8. Shopify Inbox (your chat)
Apps > install **Shopify Inbox**. Suggested quick replies, using the same wording as the site:
- "Standard Shipping: ships in 1-2 business days, then arrives in 2-7 business days."
- "Returns: 30 days. Size exchanges are free. We cover shipping both ways."

## 9. Check the theme settings
Online Store > Themes > Customize > Theme settings:
- **Returns:** window 30, conditions, exchanges, return shipping (now uses info@)
- **Availability:** in stock ships within "1-2 business days"
- **Shipping:** method "Standard Shipping", delivery time "2-7 business days", duties note
- **Brand:** contact email info@maisonrivault.com

Every page reads from these, so change wording here, never in individual pages.

**Inconsistency to resolve.** Your preorder policy (Availability > Preorder policy) says "Estimated ship dates are 2-4 weeks", but "Preorder: expected ship date" says "within 14 business days". Make them agree. I also fixed a placeholder that was visible to customers in that policy, "[Link to policy, or: ...14 days...]", and changed it to the 30-day wording.

## 10. Homepage "Signature Collection"
It's now hidden by default. To bring it back: Customize > Home page > Next collection > tick **Show this section**. The "Join the list" email signup lower on the page is unaffected.

## 11. Business details (not urgent, but worth deciding)
- **Address:** your refund policy lists 8101 E Ferzon Trl, Scottsdale. If that's a home address, it's public on every policy page. Consider a business address or virtual mailbox.
- **LLC:** consider forming one before scaling paid traffic, so chargebacks and disputes hit the business, not you personally. Talk to an Arizona accountant or attorney.

## 12. On-model photos
Upload at least one on-model photo per product, plus the cuff or stitch close-up from the checklist. The product page and cards use the first photo, so put the on-model shot first.
