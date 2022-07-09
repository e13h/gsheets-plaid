function run_plaid_link(link_token, received_redirect_uri = null) {
    const handler = Plaid.create({
        token: link_token,
        receivedRedirectUri: received_redirect_uri,
        onSuccess: (public_token, metadata) => {
            redirected_url = `${window.location.origin}/plaid-link-success?public_token=${public_token}`;
            window.location.replace(redirected_url);
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
