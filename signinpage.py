import getpass

def user_sign_in():
    """Ask a user for their username and password."""
    username = input("Please enter your user name: ")
    password = getpass.getpass("Please enter your password: ")
    print(f"Welcome, {username}!") 


def main():
    """Display the menu for the user to choose an action."""
    while True:
        print("\nWould you like to:")
        print("1. Log in")
        # print("2. Sign up for an account")
        print("3. Exit")

        user_choice = input("Please pick a choice from the list above: ")

        if user_choice == "1":
            user_sign_in()
        elif user_choice == "3":
            print("Thank you for using Chatty Chapters!\n"
                  "We hope to see you again soon.\n"
                  "Happy Reading 📖")
            break
        else:
            print("Please choose a valid input.")


if __name__ == "__main__":
    main()