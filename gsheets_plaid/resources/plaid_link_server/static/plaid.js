function run_plaid_link(link_token) {
    const handler = Plaid.create({
        token: link_token,
        onSuccess: (public_token, metadata) => {
            window.location.replace(`http://localhost:8080/success?public_token=${public_token}`);
            console.log('public_token', public_token);
            console.log('metadata', metadata);
        },
        onLoad: () => {},
        onExit: (error, metadata) => {
            console.log(error, metadata);
        },
        onEvent: (eventName, metadata) => {
            console.log("Event:", eventName);
            console.log("Metadata:", metadata);
        }
    });
    handler.open();
}
