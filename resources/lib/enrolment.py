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
			cursor: pointer;
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
			</form>
		</div>
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
			display: none;
			}
			.input {
			width: 200px;
			height: 26px;
			border: 0.6px solid black;
			background-color: #2E2E2E;
			}
			.button1 {
			height: 100%%;
			width: 100%%;
			color: white;
			border: none;
			cursor: pointer;
			background-color: transparent;
			}
			.button2 {
			width: 200px;
			height: 26px;
			margin-top: 20px;
			border: 0.6px solid black;
			background-color: #1D1D1D;
			margin-top: 21px;
			cursor: pointer;
			}
			body {
			background-color: #080808;
			}
		</style>
	</head>
	<body>
		<div class="container">
			<button class="button button1" id=google onclick="myFunction()" >
			Click to get your code then fill the next form
			</button>
			<form action="/enroll" method="post">
				<div class="inner" id=form>
					<input div class="input" style="color:white" type="text" name="account" placeholder="Account name">
					<br/>
					<br/>
					<input div class="input" style="color:white" type="text" name="code" placeholder="Google code">
					<br/>
					<input div class="button button2" style="color:white" type="submit" value="Submit">
					<input hidden div class="input" style="color:white" type="text" name="client_id" value="%s" placeholder="Client ID">
					<input hidden div class="input" style="color:white" type="text" name="client_secret" value="%s" placeholder="Client secret">
				</div>
			</form>
		</div>
	</body>
	<script>
		function myFunction() {
		var x = document.getElementById("google");
		window.open("https://accounts.google.com/o/oauth2/auth?scope=https://www.googleapis.com/auth/drive.readonly&access_type=offline&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&client_id=%s","_blank");
		x.style.display = "none";
		var x = document.getElementById("form");
		x.style.display = "block";
		}
	</script>
</html>""" % (
	clientID,
	clientSecret,
	clientID,
)
