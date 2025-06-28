from app import create_app

app = create_app()

if __name__ == "__main__":
    # DEBUG để thấy stack-trace khi bạn phá code
    app.run(debug=True)
