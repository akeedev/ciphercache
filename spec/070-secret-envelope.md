# Secret Envelope (070)

Whenever the ciphercache client returns a secret to the caller, it wraps the
secret in a secret envelope which allows secrets to be used easily but protects them from being accidentally logged or dumped.

## Semantics
A Secret is an object containing a string that must not be accidentally logged
or dumped. To achieve that, repr and str are overwritten to return "<*redacted*>"
if the secret is not empty, or "" if the secret is empty.
- A Secret has a use method that uses it in a one parameter function.
- A Secret has a reveal method that returns the secret as a string.

A SecretEnvelope is a dictionary where each value is a Secret. A SecretEnvelope
has a use method that takes a list of fields within of length n and a function
taking n parameters. It will call the function and pass in SecretEnvelope[key].reveal() for each key in the list. See Usage example below.


## Usage example
```
# assume that client is a Ciphercache client connected to a ciphercached
# assume that the secret "myauth-data" has a key called "user" and 
# a key called "password"
> secret = client.get_secret("myauth-data")
> print(secret)
{"user": "<*redacted*>", "password": "<*redacted*>"}
> print(secret["user"].reveal())
"johndoe"
# assume that authenticate is a function taking two arguments, namely user and password, then we can use the secret in the function like this:
> secret.use(['user', 'password'], authenticate)
# assume that the function use_password is a function taking one argument with the password, then we can use the secret like this:
> secret.use('password', use_password)
# or we can delegate to the corresponding Secret-object like this:
> secret["password"].use(use_password)
```
