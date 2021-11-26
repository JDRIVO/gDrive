page1 = b"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
.container {
				position: absolute;
				top: 50%;
				left: 50%;
				-moz-transform: translateX(-50%) translateY(-50%);
				-webkit-transform: translateX(-50%) translateY(-50%);
				transform: translateX(-50%) translateY(-50%);
				background-color: 080808;
				border: 1px solid black;
				height: 200px;
				width: 300px;
				background-color: #0F0F0F;
				box-shadow: 5px 10px;
}
.inner {
				position: absolute;
				top: 50%;
				left: 50%;
				-moz-transform: translateX(-50%) translateY(-50%);
				-webkit-transform: translateX(-50%) translateY(-50%);
				transform: translateX(-50%) translateY(-50%);
}
.input {
				width: 200px;
				height: 26px;
				border: 0.6px solid black;
				background-color: #2E2E2E;
}
.button {
				width: 200px;
				height: 26px;
				border: 0.6px solid black;
				background-color: #1D1D1D;
				margin-top: 21px;

}
body {
				background-color: #080808;
}
</style>
</head>
<body>
<div class="container">
<form action="/enroll?default=false" method="post">
<div class="inner">
<input div class="input" style="color:white" type="text" name="client_id" placeholder="Client ID">
<br/>
<br/>
<input div class="input" style="color:white" type="text" name="client_secret" placeholder="Client Secret">
<br/>
<input div class="button" style="color:white" type="submit" value="Submit">
</div>
</div>
</form>
</body>
</html>"""


def page2(clientID, clientSecret):
	return """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
.text {
				width: 300px;
				margin: 20 auto;
}
.container {
				position: absolute;
				top: 50%%;
				left: 50%%;
				-moz-transform: translateX(-50%%) translateY(-50%%);
				-webkit-transform: translateX(-50%%) translateY(-50%%);
				transform: translateX(-50%%) translateY(-50%%);
				background-color: 080808;
				border: 1px solid black;
				height: 200px;
				width: 300px;
				background-color: #0F0F0F;
				box-shadow: 5px 10px;
}
.inner {
				position: absolute;
				top: 50%%;
				left: 50%%;
				-moz-transform: translateX(-50%%) translateY(-50%%);
				-webkit-transform: translateX(-50%%) translateY(-50%%);
				transform: translateX(-50%%) translateY(-50%%);
}
.input {
				width: 200px;
				height: 26px;
				border: 0.6px solid black;
				background-color: #2E2E2E;
}
.button {
				width: 200px;
				height: 26px;
				margin-top: 20px;
				border: 0.6px solid black;
				background-color: #1D1D1D;
				margin-top: 21px;
}
a:link {
				color: white;
				text-decoration: none;
				font-family: Arial
}
a:hover {
				text-decoration: underline;
}
a:visited {
				color: white;
}
body {
				background-color: #080808;
}
</style>
</head>
<body>
<a href="https://accounts.google.com/o/oauth2/auth?scope=https://www.googleapis.com/auth/drive.readonly&access_type=offline&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&client_id=%s" target="_blank">
<div class="text">
Click here and paste the code in the form below and then enter an account name.
</div>
</a>
<div class="container">
<form action="/enroll" method="post">
<div class="inner">
<input div class="input" style="color:white" type="text" name="account" placeholder="Account name">
<br/>
<br/>
<input div class="input" style="color:white" type="text" name="code" placeholder="Google code">
<br/>
<input div class="button" style="color:white" type="submit" value="Submit">
<input hidden div class="input" style="color:white" type="text" name="client_id" value="%s" placeholder="Client ID">
<input hidden div class="input" style="color:white" type="text" name="client_secret" value="%s" placeholder="Client secret">
</div>
</div>
</form>
</div>
</body>
</html>""" % (
	clientID,
	clientID,
	clientSecret,
)
