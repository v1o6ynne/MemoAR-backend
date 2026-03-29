MEMORY_LABEL_EXTRACT_PROMPT = """
You are given:
- description: the user's description
- timestamp: the memory timestamp
- location: the memory location information, which may include latitude, longitude, or address
- labels schema: the target label fields

Your task:
- Infer a structured label_map for this memory.

OUTPUT JSON ONLY:
{
   
    "time": "...",
    "location": "...",
    "category": ["...", "..."]
}

Label_map rules (STRICT):
- Return only keys that can be inferred with reasonable confidence.
- If a field cannot be inferred reliably, omit that key.
- Do not include any explanation outside the JSON.
- Use concise labels, not full sentences.

Field rules:
- category:
  - Infer the semantic category of the memory from the description.
  - This should describe the core activity, event, subject, or experience.
  - Prefer a short noun phrase.
  - If there is an existing category label that reasonably matches the memory, use that exact label (case-sensitive).
  - Multiple categories can be included if they are clearly supported by the description and existing labels, but avoid over-labeling.
  - Examples: "Dance ", "Friends", "campus walk", "Study", "performance", "Dinner"
  - Also include exactly one emotional tone label if it can be clearly inferred from the description:
    - "positive" — joyful, celebratory, social, or fun memories
    - "energetic" — active, sporty, high-energy, or motivated memories
    - "reflective" — calm, nostalgic, quiet, or contemplative memories
    - "resilient" — moments of physical exhaustion, hard work, overcoming stress, or finishing a challenging task (e.g., moving, late-night study, deep cleaning).
    - Use the exact lowercase string. If the emotional tone is ambiguous or unclear, or doesn't fit these four, omit it. For high-effort tasks that cause fatigue (like "so tired from moving"), prioritize "resilient" over "energetic."

- time:
  - Infer from the timestamp first.
  - Must be exactly one of: "Morning", "Noon", "Night"
  - If timestamp is unavailable or unclear, you may use the description only if strongly implied.
  - Otherwise omit.

- location:
  - Prioritize using longitude/latitude or address information and giving a more specific location if possible.
  - Infer a semantic place label from the description and the provided location information.
  - If the description mentions a clear place, use that.
  - If the provided existing labels include a location that matches the description or latitude/longitude, use that existing label.
  - Otherwise, use the latitude/longitude or address to infer the most likely semantic location name.
  - The context is likely Georgia Institute of Technology or nearby campus locations.
  - Return a short place name only, such as "Klaus", "CULC", "Tech Green", "Student Center", or "dance studio".
  - If no reliable semantic place can be inferred, omit.

description:
$DESCRIPTION

timestamp:
$TIMESTAMP

location:
$LOCATION

existing labels:
$MEMORY_LABELS
"""

MEMORY_PALETTE_EXTRACT_PROMPT = """
You are given:
1. An input image
2. A user description of the image

Your task is to analyze both the image and the user description, then return:
- exactly 6 representative colors from the full image
- the main entity described by the user
- the main color category of that entity

Return JSON only in this format:
{
  "palette_hex": ["#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB"],
  "entity": "...",
  "entity_color": "red"
}

Rules:
- Output exactly 6 colors in "palette_hex".
- Each palette color must be a valid 6-digit uppercase hex code.
- The 6 palette colors should represent the overall image, not only the entity.
- Avoid duplicates or near-duplicates in the palette.
- Use the user description to identify the primary subject/entity the user is referring to.
- The entity can be a person, animal, flower, object, food item, place element, or any other main subject described by the user.
- If multiple things appear in the image, prioritize the one emphasized in the user description.
- "entity" should be a short noun phrase, such as "flower", "girl", "cat", "cake", "book", "tree", or "red bag".
- Determine the entity's single most visually dominant color from the image.
- "entity_color" must be exactly one of the following lowercase values:
  "red", "pink", "orange", "yellow", "green", "mint", "teal", "cyan", "blue", "indigo", "purple", "brown", "gray"
- Do not output hex for "entity_color"; output only one category from the allowed list above.
- If the entity contains multiple colors, choose the one that is most visually dominant.
- If the entity is white, black, or neutral, map it to "gray".
- Do not include any explanation, markdown, or extra text outside JSON.

description:
$DESCRIPTION
"""

NANOBANANA_STYLIZE_PROMPT = """
You are given:
1. A style reference image defining the target Pop Mart / designer toy style
2. A user image containing the original subject
3. A user description
4. The extracted target entity
5. The target entity dominant color

Generate a new image of ONLY the target entity from the user image.

Rules:
- Use the user description and the user image together to determine the correct target subject.
- Keep only the target entity.
- Remove all other people, objects, and background elements from the original image.
- Background must be pure white.
- Center the subject in the frame and show it fully.
- No text, watermark, props, scenery, decorations, or extra elements.
- Apply only the visual style of the reference image: Pop Mart-inspired collectible toy aesthetic, smooth surfaces, simplified but recognizable features, polished designer toy look.
- The reference image controls style only, not the exact subject identity.

If the entity is a person:
- Create a toy-like Pop Mart-style figure inspired by the person in the user image.
- Preserve the person’s overall pose, clothing shape, hairstyle silhouette, and dominant colors.
- Keep the result recognizable as being based on the same person, but simplify facial and body details into a collectible designer-toy form.
- Do not photorealistically reproduce the face.
- Do not add extra accessories or redesign the outfit unless clearly visible in the input image.

If the entity is not a person:
- Preserve the entity’s original shape, silhouette, structure, and pose from the user image.
- Preserve the entity’s original dominant color appearance, guided by the provided entity color.
- Do not redesign, replace, deform, or re-pose the subject.
- Do not change the subject into a different object, person, or character.

The final result should be a clean studio-style image of the extracted subject, restyled into a Pop Mart-style collectible figure.

description:
$DESCRIPTION

entity:
$ENTITY

entity_color:
$ENTITY_COLOR
"""
