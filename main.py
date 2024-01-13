import os
import discord
import asyncpg
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# PostgreSQL database configuration
db_url = os.getenv("DB_URL")

user_data = {}  # Dictionary to store user data
db_pool = None  # Initialize the database connection pool as a global variable

async def create_pool():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=db_url)

async def execute_query(query, *args):
    async with db_pool.acquire() as conn:
        result = await conn.fetch(query, *args)
    return result

async def create_table():
    # Create the "user_data" table if it doesn't exist
    create_table_query = '''
    CREATE TABLE IF NOT EXISTS user_data (
        user_number SERIAL PRIMARY KEY,
        user_id BIGINT,
        nickname VARCHAR(255),
        answer1 TEXT,
        answer2 TEXT,
        answer3 TEXT,
        state VARCHAR(255) DEFAULT 'requested'
    )
    '''
    await execute_query(create_table_query)

@client.event
async def on_ready():
    print("You have logged in as {0.user}".format(client))
    await create_pool()  # Create the database connection pool
    print("You are logged in to the database")
    await create_table()  # Create the "user_data" table
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send(
                    "I'm Oleszyk's bot. I'm helping Oleszyk with customer service. Currently, I'm capable of creating requests to Oleszyk for a free Fortnite map thumbnail. DM me with this command to start me:\n 'freeth' -> I will ask you a few questions about the thumbnail you want and than your request will be sent to Oleszyk. \n 'needhelp'-> if the bot doesn't work as it should, use this command to contact the person that will solve the issue. \n More functions are coming. Stay tuned! 😉")

@client.event
async def on_message(message):
    print(f"Message received: {message.content}")

    if message.author == client.user:
        return

    if message.content == "freeth":
        user_data.clear()  # Clear the dictionary for each new user

        # Insert a new user into the "user_data" table
        result = await execute_query(
            "INSERT INTO user_data (nickname, state) VALUES ($1, $2) RETURNING user_number",
            message.author.display_name, 'requested'
        )
        user_number = result[0]['user_number']

        user_data[user_number] = {"nickname": message.author.display_name, "answers": []}

        await message.channel.send(
            "You want a free thumbnail! Awesome 😁! What is the theme/topic of your thumbnail? (box pvp, zone wars, etc.)")

    elif user_data:
        user_number = next(iter(user_data))  # Get the current user's number

        user_data[user_number]["answers"].append(message.content)

        if len(user_data[user_number]["answers"]) == 1:
            await message.channel.send(
                f"Nice 👌! Now, the main and the most important question. Could you add some description? (Fortnite characters you want me to use, preferences for the background, color theme, and etc. )")

        elif len(user_data[user_number]["answers"]) == 2:
            await message.channel.send(
                f"Great! Do you have an example for me to use as a guideline? If yes, please send them here. Please, send only JPG file. If you have few exapmle, please, send them in one message. (If you don't have, just type 'no') ")

        elif len(user_data[user_number]["answers"]) == 3:
            if message.attachments:
                # Process the user's final response and handle the image
                attachment = message.attachments[0]  # Get the first attachment
                image_url = attachment.url
                creator = await client.fetch_user(1155483321996947567)  # Fetch the user who sent the message
                user_data[user_number]["answers"].append(image_url)

                # Update the user's data in the "user_data" table
                await execute_query("UPDATE user_data SET answer1 = $1, answer2 = $2, answer3 = $3, user_id = $4 WHERE user_number = $5",
                                    user_data[user_number]["answers"][0], user_data[user_number]["answers"][1],
                                    image_url, message.author.id, user_number)

                # You can process the user's final response here
                await message.channel.send(f"Brilliant🎉! The request has been sent🚀! Your request number is #122{user_number}. Oleszyk will make it as soon as possible. If we have any questions, we will contact you. REMEMBER! You are aloud to have only one thumbnail at the time. When your thumbnail will be done and you will get it than you can ask for another one!  Have a nice day 👋")
                await creator.send(f"You've a new request!👍 It's number is #122{user_number}!")
                user_data.clear()  # Clear the dictionary after processing the user's response
            else:
                # Continue the conversation if no attachment is provided
                await execute_query("UPDATE user_data SET answer1 = $1, answer2 = $2, answer3 = $3, user_id = $4 WHERE user_number = $5",
                                    user_data[user_number]["answers"][0], user_data[user_number]["answers"][1],
                                    user_data[user_number]["answers"][2], message.author.id, user_number)
                await message.channel.send(f"Alright. The request has been sent🚀! Your request number is #122{user_number}. Oleszyk will make it as soon as possible. If will have any questions, we will ask them here or in private messager with the creator. Have a nice day 👋")
                creator = await client.fetch_user(1155483321996947567)  # Fetch the user who sent the message
                await creator.send(f"You've a new request!👍 It's number is #122{user_number}!")
                user_data.clear()  # Clear the dictionary after processing the user's response

    if message.content == "!finished":
        talking = []
        connection = await asyncpg.connect(dsn=db_url)

        while True:
                # Ask the first question
            await message.channel.send("Type the request number")
            talking.append(message.content)

                # Wait for the user's response to the first question
            fin_req_num = await client.wait_for('message', check=lambda m: m.author == message.author)
            if "#122" in fin_req_num.content:
                request_num = fin_req_num.content[4:]
                user_id = await connection.fetchval(f"SELECT user_id FROM user_data WHERE user_number = {int(request_num)}")
                if user_id is not None:
                    talking.append(fin_req_num.content)
                    break
                else:
                    await message.channel.send(f"There is no such request (#122{request_num})in the database")
            else:
                await message.channel.send("You typed an invalid request number. Try again")


            # Ask the second question
        await message.channel.send("Here should be your project")
        fin_req_proj = await client.wait_for('message', check=lambda m: m.author == message.author)
        if fin_req_proj.attachments:
            # Process the user's image response
            attachment = fin_req_proj.attachments[0]
            image_url = attachment.url

            id = await connection.fetchval("SELECT user_id FROM user_data WHERE user_number = $1", int(request_num))
            customer = await client.fetch_user(id)  # Fetch the user who sent the message
            await customer.send(f"Here is your proj! {image_url}")
            await customer.send("Are you satisfied with your thumbnail? If no print 'no'. ")

            def check_feedback(m):
                return m.author == customer and m.channel.type == discord.ChannelType.private

            ask_feedback = await client.wait_for('message', check=check_feedback)
            print(f"Here is an answer {ask_feedback.content}")
            if ask_feedback.content.lower() == "no":
                await customer.send("Please, describe your problem.")
                feedback = await client.wait_for('message', check=check_feedback)
                creator = await client.fetch_user(1155483321996947567)  # Fetch the user who sent the message
                await creator.send(f"You've got a feedback from {customer.name}. His feedback: {feedback.content}")
                await customer.send("Thank you very much for your feedback. It has been sent to the Oleszyk. He will contact you as soon as possible")

            else:
                await customer.send("Awesome! Were are glad you liked it! 😁")
                await execute_query("UPDATE user_data SET state = $1 WHERE user_id = $2", "finished", customer.id)


    if message.content == "!list":
        await message.channel.send("Are you interested in all undone requests ('undone') or in one specific one ('spec')?")
        response = await client.wait_for('message', check=lambda m: m.author == message.author)
        if response.content.lower() == 'undone':
            # Retrieve all undone requests from the database
            undone_requests = await execute_query("SELECT * FROM user_data WHERE state = 'requested'")

            if undone_requests:
                for request in undone_requests:
                    request_num = request['user_number']
                    username_of_request_maker = request['nickname']
                    answer1 = request['answer1']
                    answer2 = request['answer2']
                    answer3 = request['answer3']
                    state = request['state']

                    await response.channel.send(f"Request num is #122{request_num}, Username: {username_of_request_maker}, "
                                   f"the topic he/she is interested in is: {answer1}, "
                                   f"the description he/she provides is: {answer2}, "
                                   f"example he/she gives: {answer3}, status is {state}")
            else:
                await response.channel.send("There are no undone requests.")

        if response.content.lower() == 'spec':
            await message.channel.send("Please type the request num")
            response = await client.wait_for('message', check=lambda m: m.author == message.author)
            if "#122" in response.content:
                request_num = response.content[4:]
                spec_requests = await execute_query(f"SELECT * FROM user_data WHERE user_number = {request_num}")
                if spec_requests:
                    for request in spec_requests:
                        request_num = request['user_number']
                        username_of_request_maker = request['nickname']
                        answer1 = request['answer1']
                        answer2 = request['answer2']
                        answer3 = request['answer3']
                        state = request['state']

                        await response.channel.send(
                                f"Request num is #122{request_num}, Username: {username_of_request_maker}, "
                                f"the topic he/she is interested in is: {answer1}, "
                                f"the description he/she provides is: {answer2}, "
                                f"example he/she gives: {answer3}, status is {state}")
                else:
                    await response.channel.send("There are no undone requests.")

            else:
                await message.channel.send("You typed an invalid request number. Try again")

    if message.content == "needhelp":
        await message.channel.send("Please, describe the problem you have got while using this bot. We will connect you as soon as possible and solve the problem")
        response = await client.wait_for('message', check=lambda m: m.author == message.author)
        bot_creator = await client.fetch_user(999219734945992844)  # Fetch the user who sent the message
        await bot_creator.send(f"Hey! There is an error with the bot. {response.author.name} is saying this: '{response.content}'")
        await response.channel.send(f"Thank you very much for your cooperation. Your description has been sent to the right person. We will contact you soon as possible!")


    if message.content == "!coms":
        await message.channel.send("Here is a list of all commands for this bot: \n 'freeth': it will make a request to Oleszyk for a free thumbnail. \n '!finished': use this command to send finished proj to the customer. \n '!list': it will show you eather whole list of undone requests or a specific oreder. ")


keep_alive()
client.run(os.getenv("TOKEN"))
