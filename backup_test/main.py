import asyncio
from Backend.ARItems.tripo_ai import image_to_model, text_to_model


async def main():
    # text → model
    result1 = await text_to_model(
        prompt="a ballerina in white dress",
        negative_prompt="low quality",
    )
    print(result1)

    # image → model
    result2 = await image_to_model(
        image_path="dance1.jpg",
    )
    print(result2)


if __name__ == "__main__":
    asyncio.run(main())


