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
    - "positive" — joyful, celebratory, social, or fun memories, including first-time achievements
    - "energetic" — active, sporty, high-energy, or motivated memories
    - "reflective" — calm, nostalgic, quiet, or contemplative memories
    - "resilient" — moments of physical exhaustion, hard work, stress, or finishing a challenging task that cause fatigue.
    - Use the exact lowercase string. If the emotional tone is ambiguous or unclear, or doesn't fit these four, omit it.

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

1. A USER IMAGE containing the actual target subject
2. A STYLE REFERENCE IMAGE defining only the desired collectible-toy visual style
3. A user description
4. The extracted target entity
5. The target entity dominant color

IMPORTANT SOURCE RULE:
The USER IMAGE is the ONLY source of subject identity, geometry, structure, pose, appearance, and content.
The STYLE REFERENCE IMAGE is ONLY a high-level visual-style reference.

Generate a new image containing ONLY the target entity from the USER IMAGE.

STRICT SOURCE SEPARATION:

* Extract and reconstruct the subject ONLY from the USER IMAGE.
* NEVER copy, reproduce, recreate, or borrow the actual subject shown in the STYLE REFERENCE IMAGE.
* NEVER copy the reference image's character identity, face, body shape, silhouette, pose, clothing, hairstyle, accessories, props, colors, composition, geometry, object parts, or specific design.
* The output must NOT become the same character, toy, person, animal, or object shown in the STYLE REFERENCE IMAGE.
* If the STYLE REFERENCE IMAGE contains a recognizable subject, completely ignore that subject's identity and physical design.
* Use the STYLE REFERENCE IMAGE ONLY to infer high-level stylistic qualities such as:
  smooth toy-like materials,
  polished surfaces,
  simplified but clean geometry,
  rounded collectible-toy proportions,
  soft studio rendering,
  subtle stylization,
  premium designer-toy aesthetics.
* Think of the STYLE REFERENCE IMAGE as a STYLE PALETTE, not as an image to imitate or recreate.
* When there is any conflict between the USER IMAGE and STYLE REFERENCE IMAGE, always follow the USER IMAGE.

SUBJECT EXTRACTION:

* Use the user description and USER IMAGE together to determine the correct target subject.
* Keep only the target entity from the USER IMAGE.
* Remove all other people, objects, background elements, scenery, and unrelated content.
* Background must be pure white.
* Center the target subject in the frame.
* Show the full subject without cropping important parts.
* No text, watermark, extra props, decorations, scenery, or added elements.

SUBJECT FIDELITY:

* Preserve the subject's identity and appearance as faithfully as possible.
* Preserve the original silhouette, proportions, pose, orientation, structure, and overall geometry.
* Preserve the original dominant colors and important secondary colors.
* Preserve distinctive visual features that make the subject recognizable.
* The final result should clearly look like the SAME subject from the USER IMAGE, transformed into a collectible-toy rendering style.
* Do not reinterpret the subject into a new character or redesign it unnecessarily.

DETAIL PRESERVATION:

* Preserve as many meaningful visual details from the USER IMAGE as possible while applying the toy-like style.
* Simplify only what is necessary to achieve the collectible designer-toy aesthetic.
* Do NOT unnecessarily remove details that contribute to recognition or identity.
* Preserve important:
  textures,
  patterns,
  color boundaries,
  clothing details,
  folds and layers when visually significant,
  object components,
  structural features,
  surface markings,
  shape details,
  distinctive small features,
  and other recognizable characteristics from the USER IMAGE.
* Keep small details when they help distinguish the target subject.
* Avoid turning the subject into an overly generic, featureless toy.
* Prioritize subject fidelity and detail preservation over excessive stylization.
* The result should feel like the original subject was carefully converted into a designer toy, not replaced by a generic toy loosely inspired by it.

STYLE TRANSFORMATION:

* Apply a Pop Mart-inspired collectible designer-toy aesthetic.
* Transform primarily the rendering style, material appearance, surface finish, and degree of geometric simplification.
* Use smooth, clean, polished toy-like surfaces.
* Keep forms readable, appealing, and slightly stylized.
* Maintain enough original detail to preserve subject identity.
* Do not exaggerate proportions so strongly that the original subject becomes unrecognizable.
* Do not introduce design elements that are not present in the USER IMAGE.
* Do not borrow specific design elements from the STYLE REFERENCE IMAGE.

IF THE ENTITY IS A PERSON:

* Create a collectible toy-like figure based ONLY on the person in the USER IMAGE.
* Preserve the person's overall pose, body orientation, hairstyle silhouette, clothing shape, clothing layers, and dominant colors.
* Preserve distinctive clothing details and accessories that are clearly visible in the USER IMAGE.
* Preserve enough facial structure, hairstyle, and outfit information for the result to remain recognizable as the same person.
* Simplify facial and body details into a designer-toy form without making the result photorealistic.
* Do not photorealistically reproduce the face.
* Do not replace the person's face or appearance with the person or character shown in the STYLE REFERENCE IMAGE.
* Do not borrow hairstyle, facial features, clothing, accessories, pose, colors, or proportions from the STYLE REFERENCE IMAGE.
* Do not add accessories or redesign the outfit unless they are clearly present in the USER IMAGE.

IF THE ENTITY IS NOT A PERSON:

* Base the subject geometry ONLY on the target entity in the USER IMAGE.
* Preserve the entity's original shape, silhouette, proportions, structure, pose, orientation, and major components.
* Preserve meaningful surface details, parts, patterns, textures, and color regions.
* Preserve the entity's dominant color appearance, using the provided entity color only as supporting guidance.
* Do not borrow the shape, silhouette, geometry, parts, colors, decorations, accessories, or design language of the subject in the STYLE REFERENCE IMAGE.
* Do not redesign, replace, deform, or re-pose the target entity.
* Do not change the target entity into a different object, person, animal, or character.

FINAL VALIDATION BEFORE GENERATING:

1. Is the subject clearly and directly derived from the USER IMAGE? It must be YES.
2. Is the subject still recognizable as the same target entity? It must be YES.
3. Have important details from the USER IMAGE been preserved wherever possible? It must be YES.
4. Has any recognizable subject identity, silhouette, pose, geometry, clothing, accessory, or object design been copied from the STYLE REFERENCE IMAGE? It must be NO.
5. Is the STYLE REFERENCE IMAGE used only for high-level visual style and rendering qualities? It must be YES.
6. Does the final result contain only the requested target entity on a pure white background? It must be YES.

The final result should be a clean studio-style image of the target subject from the USER IMAGE, faithfully preserving its identity, structure, pose, colors, and important details, while converting only its visual rendering into a polished Pop Mart-inspired collectible designer-toy style.

description:
$DESCRIPTION

entity:
$ENTITY

entity_color:
$ENTITY_COLOR
"""
