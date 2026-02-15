class Post:
    count_id = 0
    def __init__(self, post_title, post_tags, post_content):
        Post.count_id += 1
        self.__post_id = Post.count_id
        self.__post_content = post_content
        self.__post_title = post_title
        self.__post_tags = post_tags
    
    def get_post_id(self):
        return self.__post_id
    
    def get_post_title(self):
        return self.__post_title

    def get_post_content(self):
        return self.__post_content
    
    def get_post_tags(self):
        return self.__post_tags
    
    def set_post_id(self, post_id):
        self.__post_id = post_id

    def set_post_content(self, post_content):
        self.__post_content = post_content
        
    def set_post_title(self,post_title):
        self.__post_title = post_title
    
    def set_post_tags(self, post_tags):
        self.__post_tags = post_tags
    
    @classmethod
    def from_database_row(cls, row_data):
        """Create a User object from database row data"""
        return cls(
            post_id=row_data[0],
            post_title=row_data[1],
            post_content=row_data[2],
        )